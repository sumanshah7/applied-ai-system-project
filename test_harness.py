"""
Reliability test harness for DocuBot (stretch feature).

Runs the system against a fixed set of labelled inputs and prints a pass/fail
summary plus a confidence signal for each case. It covers three behaviours the
project cares about:

- RETRIEVE : a real question must surface the expected source file.
- REFUSE   : an out-of-scope question must trigger the "I do not know" guardrail
             instead of returning a confident-looking but unsupported snippet.
- AGENT    : the agentic workflow must reach the same refuse/answer decision.

Run it with:
    python test_harness.py

Exits with a non-zero status if any case fails, so it can be used in CI.
"""

import sys

from docubot import DocuBot
from agent import DocuBotAgent

EXTRA_DOC_FOLDERS = ["knowledge"]
TOP_K = 3

# Each case: (query, kind, expected, known_gap)
#   kind "retrieve": expected is a filename that must appear in the results.
#   kind "refuse":   expected is None; retrieval must return nothing.
#   known_gap=True:  a documented limitation. It is reported separately and
#                    does NOT fail the build, so real regressions stay visible.
TEST_CASES = [
    ("Where is the auth token generated?",            "retrieve", "docs/AUTH.md", False),
    ("What environment variables are required for authentication?", "retrieve", "docs/AUTH.md", False),
    ("Which endpoint lists all users?",               "retrieve", "docs/API_REFERENCE.md", False),
    ("How do I connect to the database?",             "retrieve", "docs/DATABASE.md", False),
    # Known gap: term-frequency scoring pulls "users table" toward the
    # API_REFERENCE "User Data Endpoints" section instead of the DATABASE
    # schema. Documented in model_card.md as a retrieval limitation.
    ("Which fields are stored in the users table?",   "retrieve", "docs/DATABASE.md", True),
    # These two live only in the extra knowledge/ source (RAG enhancement):
    ("What is the rate limit on public endpoints?",   "retrieve", "knowledge/DEPLOYMENT.md", False),
    ("How do I roll back a bad deployment?",          "retrieve", "knowledge/DEPLOYMENT.md", False),
    # Out-of-scope questions must be refused, not answered:
    ("Is there any mention of payment processing?",   "refuse",   None, False),
    ("What is the weather today?",                     "refuse",   None, False),
    ("How much does the premium subscription cost?",   "refuse",   None, False),
]


def evaluate_case(bot, agent, query, kind, expected, known_gap):
    """Return a dict describing the outcome of one test case."""
    scored = bot.retrieve_scored(query, top_k=TOP_K)
    files = [f for _, f, _ in scored]
    confidence = scored[0][0] if scored else 0

    agent_result = agent.run(query, top_k=TOP_K)

    if kind == "retrieve":
        passed = (expected in files) and not agent_result["refused"]
        detail = f"expected {expected} in {files}"
    else:  # refuse
        passed = (len(files) == 0) and agent_result["refused"]
        detail = f"expected refusal; retrieved {files or 'nothing'}"

    return {
        "query": query,
        "kind": kind,
        "confidence": confidence,
        "passed": passed,
        "known_gap": known_gap,
        "detail": detail,
    }


def status_label(r):
    if r["passed"]:
        return "PASS"
    return "KNOWN GAP" if r["known_gap"] else "FAIL"


def main():
    bot = DocuBot(extra_folders=EXTRA_DOC_FOLDERS)
    # Offline agent (no LLM) keeps the harness reproducible without an API key.
    agent = DocuBotAgent(bot, llm_client=None)

    results = [evaluate_case(bot, agent, *case) for case in TEST_CASES]

    # A "real" case is one we expect to pass. Known gaps are tracked separately.
    real = [r for r in results if not r["known_gap"]]
    passed = sum(1 for r in real if r["passed"])
    total = len(real)
    regressions = [r for r in real if not r["passed"]]
    known_gaps = [r for r in results if r["known_gap"]]

    print("\nDocuBot Reliability Test Harness")
    print("================================\n")
    print(f"| {'Result':9} | {'Kind':8} | {'Conf':4} | Query")
    print(f"|{'-'*11}|{'-'*10}|{'-'*6}|{'-'*40}")
    for r in results:
        print(f"| {status_label(r):9} | {r['kind']:8} | {r['confidence']:>4} | {r['query']}")

    print(f"\nSummary: {passed}/{total} expected cases passed "
          f"({passed / total:.0%}); {len(known_gaps)} documented known gap(s).")

    ret = [r for r in results if r["kind"] == "retrieve"]
    if ret:
        avg = sum(r["confidence"] for r in ret) / len(ret)
        print(f"Average confidence on answerable queries: {avg:.2f}")

    if regressions:
        print("\nRegressions (unexpected failures):")
        for r in regressions:
            print(f"  - {r['query']}  ({r['detail']})")
    if known_gaps:
        print("\nKnown gaps (documented limitations, not build failures):")
        for r in known_gaps:
            print(f"  - {r['query']}  ({r['detail']})")

    # Only unexpected failures break the build.
    return 0 if not regressions else 1


if __name__ == "__main__":
    sys.exit(main())
