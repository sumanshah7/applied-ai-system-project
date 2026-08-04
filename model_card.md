# DocuBot Model Card

Design, evaluation, and responsible-AI reflection for the DocuBot applied AI
system. Technical sections are filled in. Sections marked **✍️ Your reflection**
are personal and graded on your own experience — write them in the first person.

---

## 1. System Overview

**What is DocuBot trying to do?**
DocuBot answers developer questions about a codebase by retrieving relevant
documentation snippets and generating a grounded answer from only those
snippets. Its goal is reliability over fluency: it would rather say "I do not
know" than produce a confident but unsupported answer.

**What inputs does DocuBot take?**
A natural-language developer question; a documentation corpus loaded from the
`docs/` and `knowledge/` folders; and an optional `GEMINI_API_KEY` environment
variable that enables the LLM-backed modes.

**What outputs does DocuBot produce?**
Either (a) a grounded answer with the source file(s) it relied on, or (b) an
explicit refusal, `"I do not know based on the docs I have."` In agentic mode it
also emits a step-by-step reasoning trace.

---

## 2. Retrieval Design

**How does retrieval work?**
- **Index:** `build_index()` builds an inverted index mapping each
  plural-normalized, lowercased word to the files it appears in, so scoring only
  considers candidate files that share a word with the query.
- **Snippets:** documents are split into paragraph-sized chunks
  (`split_into_snippets()`), so a small, citable section is returned rather than
  a whole file.
- **Scoring:** `score_document()` counts how many *distinct, meaningful* query
  words appear in a snippet. Stopwords ("the", "how", "docs"...) are dropped and
  plurals are normalized (`tokens` → `token`) so scoring focuses on topical words.
- **Selection:** `retrieve_scored()` keeps only snippets with score > 0 and
  returns the top-k with their scores (used as a confidence signal).

**Trade-offs.**
Word-overlap scoring is fast, transparent, and dependency-free (no embeddings),
which makes it easy to debug and fully reproducible. The cost is no semantic
understanding: synonyms and intent can mislead it (see §6). We chose
transparency and reproducibility over semantic recall for this project.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM?**
- **Naive LLM mode (1):** sends the question to Gemini with no retrieval.
- **Retrieval only (2):** no LLM; returns snippets directly.
- **RAG mode (3):** retrieves first, then Gemini answers using only the snippets.
- **Agentic mode (4):** deterministic Python plans/retrieves/self-checks; the LLM
  is used only for the final generation step (and is optional — it falls back to
  a snippet-based answer offline).

**How is the LLM kept grounded?**
The RAG prompt (`llm_client.answer_from_snippets`) instructs the model to use
**only** the provided snippets, to **not invent** endpoints or config values, to
reply exactly `"I do not know based on the docs I have."` when the snippets are
insufficient, and to cite which files it relied on.

---

## 4. Experiments and Comparisons

Same queries across modes. Retrieval-only and agentic observations are measured
offline (no API key). **✍️ Run modes 1 and 3 with your own key and confirm/adjust
the naive-LLM and RAG columns.**

| Query | Naive LLM (Mode 1) | Retrieval only (Mode 2) | RAG (Mode 3) | Agentic (Mode 4) |
|------|------|------|------|------|
| Where is the auth token generated? | ✍️ Confirm — tends to sound right but may invent function/file names | Returns AUTH.md snippet; accurate but raw | ✍️ Confirm — should cite AUTH.md, name `generate_access_token` | Answers, confidence 2, grounding 0.89 |
| How do I connect to the database? | ✍️ Confirm — may guess a generic connection string | Returns DATABASE.md snippet | ✍️ Confirm — grounded in DATABASE.md | Answers from DATABASE.md |
| What is the rate limit on public endpoints? | ✍️ Confirm — likely a plausible guess (no such knowledge) | Returns knowledge/DEPLOYMENT.md (100 req/min, 429) | ✍️ Confirm — grounded, cites DEPLOYMENT.md | Answers, confidence 4 |
| Is there any mention of payment processing? | ✍️ Confirm — may hallucinate a payments flow | Refuses (no snippets) | ✍️ Confirm — should refuse | Refuses (confidence 0) |

**Patterns observed.**
- **Naive LLM** looks impressive but is weakly grounded — it answers even when
  the docs contain nothing on the topic.
- **Retrieval only** is accurate and evidence-based but raw: it dumps snippets
  and leaves interpretation to the reader.
- **RAG / agentic** balance the two — a readable answer *tied to* cited snippets,
  with an explicit refusal when evidence is missing.

---

## 5. Failure Cases and Guardrails

**Failure case 1 — semantic mismatch (documented known gap).**
*Question:* "Which fields are stored in the users table?"
*What happens:* retrieval returns `API_REFERENCE.md` (which has a "User Data
Endpoints" section) instead of `DATABASE.md`. Word-overlap scoring can't tell
"users table = schema" from "user endpoints."
*Should happen:* return the DATABASE.md schema. Tracked as a `known_gap` in
`test_harness.py`.

**Failure case 2 — tie-breaking by document order.**
*Question:* "Where is the auth token generated?"
*What happens:* the exact "Token Generation" section and a "TOKEN_LIFETIME"
snippet tie on score, so the tiebreak is arbitrary.
*Should happen:* the definition section should rank first (needs term-frequency
or heading weighting).

**When should DocuBot refuse?**
- When no retrieved snippet contains any meaningful query word (out-of-scope
  topic, e.g. payments, weather).
- When retrieval confidence stays below threshold even after the agent
  reformulates and retries.

**Guardrails implemented.**
- Zero-score snippets are dropped → empty retrieval → explicit refusal.
- Agentic confidence threshold with a single reformulation retry before refusing.
- Grounding self-check on generated answers; a low ratio appends a caution note.
- RAG prompt forbids inventing facts and mandates the exact refusal string.

---

## 6. Limitations and Future Improvements

**Current limitations**
1. **No semantic understanding.** Word-overlap retrieval misses synonyms and
   confuses similar-sounding topics (the users-table gap above).
2. **Small, curated corpus.** Results reflect only what's in `docs/` and
   `knowledge/`; coverage bias means confident answers on covered topics and
   refusals everywhere else.
3. **Shallow confidence signal.** "Confidence" is just the top word-overlap
   count, not a calibrated probability.
4. **Heuristic query expansion.** The agent's synonym map is hand-written and
   small; it won't generalize to unseen vocabulary.

**Future improvements**
1. Add embedding-based semantic retrieval (or hybrid lexical + semantic).
2. Weight scores by term frequency / heading position to fix tie-breaking.
3. Expand the evaluation set and add regression tracking over time.

---

## 7. Responsible-AI Reflection

*(Required by the project rubric — labeled sections below.)*

### 7.1 Limitations and biases
Covered in §6. In short: the system is only as good as its corpus (coverage
bias), and its lexical retrieval has no semantic understanding, so it can
retrieve the wrong-but-lexically-similar section. It presents a numeric
"confidence" that is not statistically calibrated and should not be read as a
probability of correctness.

### 7.2 Could this AI be misused, and how would you prevent it?
Risks: a developer could over-trust an answer and ship an insecure change (e.g.
mishandling `AUTH_SECRET_KEY`); or the corpus could be poisoned with incorrect
docs, causing confidently wrong answers. Preventions in place / recommended:
strict grounding (answers only from retrieved snippets), mandatory source
citations so users can verify, an explicit refusal path, and — for real use —
treating outputs as pointers to the docs, not as authority, plus review of what
goes into the corpus.

### 7.3 ✍️ What surprised you while testing your AI's reliability?
> _Write 3-5 sentences in the first person. (A candidate observation from the
> build: most reliability gains came from retrieval quality and the refusal
> rule, not from the model — but say what actually surprised **you** when you
> ran it.)_

### 7.4 ✍️ Your collaboration with AI on this project
> _Describe how you used an AI coding assistant. Give **one specific helpful
> suggestion** it made and **one specific flawed or incorrect suggestion**, and
> how you caught/handled the flawed one. Write in the first person — this is
> graded on your own experience._

---
