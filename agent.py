"""
Agentic workflow for DocuBot (stretch feature).

Instead of a single retrieve-then-answer pass, the agent runs a small
plan -> act -> check -> (retry) loop and records a reasoning trace for every
step:

1. PLAN   - turn the raw question into one or more search queries, bridging
            user vocabulary to documentation vocabulary (e.g. "sign in"
            -> "login").
2. ACT    - retrieve scored snippets for each planned query and merge them,
            keeping the best score per snippet. The top score is used as a
            simple confidence signal.
3. CHECK  - if confidence is too low, reformulate once and retry (ACT again).
            If it is still too low, refuse instead of guessing.
4. ANSWER - generate a grounded answer (via Gemini when available, otherwise
            from the retrieved snippets) and self-check that the answer is
            actually supported by the retrieved evidence.

The agent runs fully offline (no API key required) so the workflow is
reproducible and testable. When a GeminiClient is supplied it is used for the
final generation step; the planning, retrieval, and grounding checks are
deterministic Python.

Reasoning traces are appended to ai_interactions.md so they can be reviewed
without re-running the system (stretch requirement).
"""

import os
from datetime import datetime

from docubot import tokenize, STOPWORDS

# Bridge common question vocabulary to the words that actually appear in the
# docs. Used to reformulate a query when the first retrieval is weak.
SYNONYMS = {
    "signin": ["login"],
    "signup": ["register"],
    "login": ["authenticate", "credentials"],
    "auth": ["authentication", "token"],
    "db": ["database"],
    "connect": ["connection", "database_url"],
    "route": ["endpoint"],
    "endpoint": ["route"],
    "deploy": ["deployment", "gunicorn", "container"],
    "rollback": ["roll", "previous"],
    "throttle": ["rate", "limit"],
}

# If the best retrieval score is below this, the agent reformulates and retries.
CONFIDENCE_THRESHOLD = 2

# Minimum fraction of the answer's meaningful words that must appear in the
# retrieved snippets for the answer to count as "grounded".
GROUNDING_THRESHOLD = 0.4

REFUSAL = "I do not know based on the docs I have."

TRACE_LOG = "ai_interactions.md"


class DocuBotAgent:
    def __init__(self, bot, llm_client=None, log_path=TRACE_LOG):
        """
        bot:        a DocuBot instance (provides retrieval + scoring).
        llm_client: optional GeminiClient for the final generation step.
        log_path:   file to append reasoning traces to.
        """
        self.bot = bot
        self.llm_client = llm_client
        self.log_path = log_path

    # -----------------------------------------------------------
    # Step 1: PLAN
    # -----------------------------------------------------------

    def plan_queries(self, query):
        """
        Produce an ordered list of search queries to try.
        The original query is always first; a synonym-expanded variant is
        added as a fallback so a later retry can broaden the search.
        """
        meaningful = [w for w in tokenize(query) if w not in STOPWORDS]

        expanded = list(meaningful)
        for word in meaningful:
            expanded.extend(SYNONYMS.get(word, []))

        plans = [query]
        if expanded != meaningful:
            plans.append(" ".join(expanded))
        return plans

    # -----------------------------------------------------------
    # Step 2: ACT
    # -----------------------------------------------------------

    def retrieve_merged(self, planned_query, top_k):
        """
        Retrieve scored snippets and return them plus a confidence signal
        (the best score seen). Deterministic and offline.
        """
        scored = self.bot.retrieve_scored(planned_query, top_k=top_k)
        confidence = scored[0][0] if scored else 0
        return scored, confidence

    # -----------------------------------------------------------
    # Step 4 helper: self-check grounding
    # -----------------------------------------------------------

    def grounding_ratio(self, answer, snippets):
        """
        Fraction of the answer's meaningful words that also appear in the
        retrieved snippets. A low ratio means the answer drifted beyond its
        evidence. Returns 1.0 for an empty answer to avoid false alarms.
        """
        answer_words = {w for w in tokenize(answer) if w not in STOPWORDS}
        if not answer_words:
            return 1.0

        snippet_words = set()
        for _, _, snippet in snippets:
            snippet_words.update(tokenize(snippet))

        supported = sum(1 for w in answer_words if w in snippet_words)
        return supported / len(answer_words)

    # -----------------------------------------------------------
    # Orchestration
    # -----------------------------------------------------------

    def run(self, query, top_k=3):
        """
        Execute the full plan -> act -> check -> answer loop.
        Returns a dict: {answer, refused, confidence, snippets, trace}.
        """
        trace = []
        plans = self.plan_queries(query)
        trace.append(f"PLAN: generated {len(plans)} search query(ies): {plans}")

        snippets, confidence, used_query = [], 0, None

        # ACT + CHECK: try each planned query until confidence clears the bar.
        for attempt, planned in enumerate(plans, start=1):
            snippets, confidence = self.retrieve_merged(planned, top_k)
            files = [f for _, f, _ in snippets]
            trace.append(
                f"ACT (attempt {attempt}): query={planned!r} -> "
                f"confidence={confidence}, snippets from {files or 'none'}"
            )
            used_query = planned
            if confidence >= CONFIDENCE_THRESHOLD:
                trace.append(
                    f"CHECK: confidence {confidence} >= {CONFIDENCE_THRESHOLD}; "
                    "proceeding to answer."
                )
                break
            trace.append(
                f"CHECK: confidence {confidence} < {CONFIDENCE_THRESHOLD}; "
                "reformulating." if attempt < len(plans)
                else f"CHECK: confidence {confidence} < {CONFIDENCE_THRESHOLD} "
                     "and no reformulations left."
            )

        # Guardrail: no evidence at all -> refuse rather than guess.
        if not snippets:
            trace.append("DECIDE: no supporting snippets found -> refusing.")
            result = {
                "answer": REFUSAL,
                "refused": True,
                "confidence": 0,
                "snippets": [],
                "trace": trace,
            }
            self._log(query, result)
            return result

        # ANSWER: generate from evidence (LLM if available, else snippets).
        pairs = [(f, s) for _, f, s in snippets]
        if self.llm_client is not None:
            answer = self.llm_client.answer_from_snippets(query, pairs)
            source = "Gemini (RAG)"
        else:
            answer = self._answer_from_snippets_offline(pairs)
            source = "offline (retrieved snippets)"
        trace.append(f"ANSWER: generated via {source}.")

        # Self-check grounding of the generated answer.
        ratio = self.grounding_ratio(answer, snippets)
        trace.append(f"SELF-CHECK: grounding ratio = {ratio:.2f}")
        if ratio < GROUNDING_THRESHOLD and self.llm_client is not None:
            note = ("\n\n[Agent note: this answer may not be fully supported by "
                    "the retrieved docs. Treat it with caution.]")
            answer += note
            trace.append(
                "SELF-CHECK: grounding below threshold -> appended caution note."
            )

        result = {
            "answer": answer,
            "refused": False,
            "confidence": confidence,
            "snippets": [f for f, _ in pairs],
            "trace": trace,
        }
        self._log(query, result)
        return result

    # -----------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------

    def _answer_from_snippets_offline(self, pairs):
        """Deterministic 'answer' when no LLM is configured: the evidence itself."""
        blocks = [f"[{filename}]\n{text}" for filename, text in pairs]
        return "Based on the retrieved documentation:\n\n" + "\n---\n".join(blocks)

    def _log(self, query, result):
        """Append the reasoning trace to ai_interactions.md."""
        try:
            with open(self.log_path, "a", encoding="utf8") as f:
                f.write(f"\n## {datetime.now().isoformat(timespec='seconds')} — {query}\n\n")
                f.write(f"- Refused: {result['refused']}\n")
                f.write(f"- Confidence: {result['confidence']}\n")
                f.write(f"- Sources: {result['snippets']}\n\n")
                f.write("Reasoning trace:\n\n")
                for step in result["trace"]:
                    f.write(f"1. {step}\n")
                f.write("\n---\n")
        except OSError:
            # Logging must never break the main answer path.
            pass
