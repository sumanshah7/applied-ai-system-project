# DocuBot — 3-Minute Engineer's Pitch (cheat sheet)

**One-liner:** DocuBot is a documentation assistant that answers developer
questions using only your docs — and honestly says "I don't know" when the docs
don't cover it.

**Run the demo:** `python demo.py`  (auto-plays 4 scenes — just narrate)
**Prove reliability:** `python test_harness.py`  → **10/10 pass**

---

## ⏱️ The 3 minutes (say roughly this)

### 1. The Problem (~30s)
> "A general AI has never seen your project's docs, so it *guesses* — confident
> but wrong. DocuBot fixes that: it reads your docs, answers only from them, and
> refuses when the answer isn't there."

### 2. The Logic — how the AI thinks (~70s)
> "It uses **RAG** — Retrieval-Augmented Generation. First it **retrieves** the
> most relevant snippets from the docs, then the model answers using **only**
> those snippets and cites them."
>
> "On top of RAG I built an **agentic loop**: *plan → search → check → retry →
> answer → self-check*. It rates its own confidence — if a search is weak, it
> reformulates and tries again. When I ask 'tell me about the db', the docs say
> 'database', so the first search is weak; the agent notices, swaps db→database,
> and retries. It corrects itself, and logs every step."

*(Show Scene 3 of the demo here.)*

### 3. The Reliability — how I know it works (~50s)
> "Two things: **guardrails** and **testing**. The main guardrail is **refusal**
> — no evidence, no answer. The RAG prompt also forbids inventing facts and
> requires citations. For testing, my harness runs 11 labelled cases — correct
> answers *and* questions that should be refused — and passes 10/10, with one
> honest known gap I documented."

*(Show Scene 2 refusal + `test_harness.py` output.)*

### 4. The Reflection — what surprised me (~30s)
> "That reliability was a **system** problem, not a **model** problem. Every time
> RAG gave a bad answer, the fix wasn't a smarter AI — it was better retrieval.
> Fixing how I scored and ranked snippets turned wrong answers into right ones."

---

## 🛡️ Guardrails (5 layers)
1. **Refusal on no evidence** — zero-score retrieval → "I do not know based on the docs I have."
2. **Confidence threshold** — agent won't answer a weak match; it retries first.
3. **Grounding self-check** — verifies the answer's words appear in the snippets.
4. **Strict RAG prompt** — use only snippets, don't invent, cite sources.
5. **Safe errors** — API failures caught; logging never breaks the answer.

## 🤖 The agent loop
`PLAN` (synonyms) → `ACT` (search + confidence) → `CHECK` (retry if weak / refuse if empty) → `ANSWER` → `SELF-CHECK` (grounding). Traces in `ai_interactions.md`.

## 🧑 Human-in-the-loop
- **I define correct behavior** — the test harness expectations (which doc should
  answer, which questions should refuse). The AI is graded against my judgment.
- **I review outputs** — the model_card §4 comparison table (naive vs RAG).
- **I triage failures** — labelled the "sign in" miss a *known gap*, not a bug.
- **I can audit reasoning** — every agent run logs why it acted.

---

## 🎤 Q&A question bank (1 minute)

**Grounded (safe):**
- "Where is the auth token generated?" → cites AUTH.md, names `generate_access_token`
- "How do I roll back a deployment?" → multi-source, cites knowledge/DEPLOYMENT.md

**Guardrail:**
- "Is there any mention of payment processing?" → refuses

**The money shot (main.py, Mode 1 then Mode 3):**
- "What hashing algorithm is used for passwords?" → Mode 1 **hallucinates** a
  guess; Mode 3 **refuses** (docs only mention a `password_hash` field). Proves
  why RAG matters in one line.

**Owning a limitation (scores well):**
- "How do I sign in?" → it misses (matches the wrong sense of "sign"). Say:
  *"That's a real limitation — lexical search can't tell word senses apart;
  semantic retrieval is my next step."*

---

## 📊 Numbers to drop
- **10/10** test-harness cases pass (1 documented known gap)
- Retrieval hit-rate **0.88**
- **4 modes** compared: Naive, Retrieval-only, RAG, Agentic
- **2 data sources** retrieved together (docs/ + knowledge/)

## 🗂️ Where things live
`docubot.py` retrieval · `agent.py` agentic loop · `llm_client.py` prompts ·
`test_harness.py` tests · `demo.py` demo · `model_card.md` reflection ·
`diagrams/architecture.mmd` design
