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
- **Scoring:** `score_document()` uses **term-frequency**: it sums how often the
  query's meaningful words occur in a snippet, so a section that discusses a
  topic repeatedly outranks a passing mention. Stopwords ("the", "how",
  "docs"...) are dropped, plurals are normalized (`tokens` → `token`), and
  identifiers are split on underscores (`generate_access_token` →
  `generate, access, token`) so a question about a "token" can find the function
  that generates it.
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

Same queries across modes. Retrieval-only and agentic results are measured
directly (offline). Naive behaviour follows from the code: Mode 1's prompt
(`naive_answer_over_full_docs`) **ignores the docs entirely** and asks the model
generically — so it answers purely from the model's general knowledge, with no
grounding and no citations. RAG (Mode 3) results reflect a live run plus the
snippets retrieval now feeds the model.

| Query | Naive LLM (Mode 1) | Retrieval only (Mode 2) | RAG (Mode 3) | Agentic (Mode 4) |
|------|------|------|------|------|
| Where is the auth token generated? | Ungrounded — answers from general knowledge, no citation, may invent a file/function | Top snippet = AUTH.md "Token Generation" (score 4); accurate but raw | Grounded: names `generate_access_token` in `auth_utils.py`, cites AUTH.md * | Answers, confidence 4, cites AUTH.md |
| What is the rate limit on public endpoints? | Guesses a plausible number (no real knowledge) | knowledge/DEPLOYMENT.md — 100 req/min, HTTP 429 | Grounded, cites DEPLOYMENT.md (**multi-source**) | Answers, confidence 4 |
| Is there any mention of payment processing? | May hallucinate a payments flow | Refuses (no snippets) | **"I do not know based on these docs"** (confirmed live) | Refuses (confidence 0) |
| How do I sign in? | Describes a generic login flow | **Known gap** — returns AUTH_SECRET_KEY *signing* snippets, misses `/api/login` | Refused ("I do not know") — the signing snippets don't support a login answer, so the grounding rule caught the retrieval miss (confirmed live) | Same: refuses, since the wrong-sense snippets don't answer the question |

\* Before the retrieval improvement (term-frequency + underscore splitting), RAG
*hedged* on the auth-token question because the correct "Token Generation"
section tied on score and fell out of the top-3. Fixing retrieval — not the
model — turned the hedge into a grounded answer. This is the clearest evidence
in the project that **grounding quality is a retrieval problem, not a model
problem.**

**Patterns observed.**
- **Naive LLM** looks impressive but is weakly grounded — it answers even when
  the docs contain nothing on the topic, and never cites a source.
- **Retrieval only** is accurate and evidence-based but raw: it returns snippets
  and leaves interpretation to the reader (and can surface the wrong *sense* of
  a word, as in "sign in").
- **RAG / agentic** balance the two — a readable answer *tied to* cited snippets,
  with an explicit refusal when evidence is missing. They are only as reliable
  as the snippets retrieval hands them (see the "sign in" row).

---

## 5. Failure Cases and Guardrails

**Failure case 1 — word-sense / polysemy (current known gap).**
*Question:* "How do I sign in?"
*What happens:* retrieval returns snippets about `AUTH_SECRET_KEY` — "a secret
used to **sign** all access tokens" — because "sign in" lexically matches the
*cryptographic* sense of "sign." The actual login endpoint (`POST /api/login` in
API_REFERENCE.md) is never retrieved.
*Should happen:* return the login workflow. Lexical scoring fundamentally cannot
disambiguate word senses; only semantic (embedding-based) retrieval would.
Tracked as a `known_gap` in `test_harness.py`.
*Silver lining:* in RAG mode the grounding rule caught the miss — given the
wrong-sense snippets, the model refused ("I do not know") rather than inventing a
login answer. So retrieval failed, but the guardrail prevented a *misleading*
answer; the residual failure is a false refusal (missing an answerable question),
not a confident wrong answer.

**Failure case 2 — naive generation is ungrounded by construction.**
*Question:* any (e.g. "What is the rate limit?").
*What happens:* Mode 1's prompt ignores the docs and answers from the model's
general knowledge, so it will confidently answer even topics the docs never
cover, with no citation.
*Should happen:* this is exactly why the project uses RAG — retrieval forces the
answer to be grounded in and cite real snippets, and to refuse when there are
none.

**Previously documented, now fixed.** Earlier versions missed the "users table"
schema (pulled toward "User Data Endpoints") and let the auth-token "Token
Generation" section lose a score tie. Both were resolved by term-frequency
scoring plus splitting identifiers on underscores — see §2 and the §4 footnote.

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

### 7.3 What surprised you while testing your AI's reliability?

*(Written from what actually happened while building and testing — adjust to
your own voice.)*

The biggest surprise was that reliability was almost entirely a **retrieval**
problem, not a model problem. In RAG mode I asked "Where is the auth token
generated?" — a question the docs clearly answer — and the model *refused to
answer confidently*, because the scoring tie bumped the correct "Token
Generation" section out of the top-3 snippets. I fixed it by changing the
**scoring** (term-frequency + splitting identifiers on underscores), not the
model, and the hedge became a correct grounded answer. I was also surprised that
the "naive" mode's prompt ignores the documentation entirely, yet still sounds
authoritative — a good reminder that fluent output is not evidence of grounding.
Finally, the "sign in" word-sense gap surprised me: retrieval confidently
returned snippets about cryptographically *signing* tokens, which lexical
scoring simply cannot tell apart from *signing in*.

### 7.4 Your collaboration with AI on this project

*(Written from the real build process — adjust to your own voice.)*

I used an AI coding assistant throughout to design and implement the retrieval
pipeline, the agentic loop, and the test harness, while I decided what behaviour
was actually correct.

- **One helpful suggestion:** when a real retrieval miss ("users table" pulling
  the wrong file) showed up in testing, the assistant suggested tracking it as a
  labelled **known gap** in the harness — reported separately and not counted as
  a build failure — so a documented limitation stays visible without hiding it
  or faking a green build. That framing (regressions vs. known gaps) made the
  test output both honest and clean.
- **One flawed suggestion:** the assistant's first attempt to demonstrate the
  multi-source RAG enhancement used the query "How do I deploy the application?"
  as a before/after example. It looked like it worked, but it was a **false
  positive** — the query matched the generic word "application" (and "docs"),
  so *both* the before and after runs returned something, which didn't actually
  prove the new `knowledge/` source was being used. I caught it by inspecting
  which words were matching, added those filler words to the stopword list, and
  switched to a query ("What is the rate limit on public endpoints?") whose
  meaningful words appear *only* in the new source — giving a genuine
  refuse-then-answer before/after.

---
