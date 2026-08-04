# Agent Reasoning Traces

This file documents the intermediate reasoning of DocuBot's **agentic workflow**
(`agent.py`, Mode 4). For every question the agent runs a
`plan -> act -> check -> (retry) -> answer -> self-check` loop and records each
step. Running the agent (via `python main.py` Mode 4, or `python test_harness.py`)
**appends live traces to the bottom of this file automatically**.

Below are three representative, hand-picked traces that show the workflow's
distinct behaviours: a direct answer, a reformulation/retry, and a refusal.

---

## Trace 1 — Direct answer (confidence clears the bar on the first attempt)

**Question:** Where is the auth token generated?

```
PLAN:  generated 2 search query(ies):
       ['Where is the auth token generated?',
        'auth token generated authentication token']
ACT (attempt 1): query='Where is the auth token generated?'
       -> confidence=2, snippets from ['docs/AUTH.md', 'docs/API_REFERENCE.md']
CHECK: confidence 2 >= 2; proceeding to answer.
ANSWER: generated via offline (retrieved snippets).
SELF-CHECK: grounding ratio = 0.89
```

The first query is strong enough (confidence 2), so no reformulation is needed.

---

## Trace 2 — Reformulation / retry (first attempt is weak, synonym expansion rescues it)

**Question:** Tell me about the db

```
PLAN:  generated 2 search query(ies):
       ['Tell me about the db', 'tell me about db database']
ACT (attempt 1): query='Tell me about the db'
       -> confidence=1, snippets from ['docs/DATABASE.md']
CHECK: confidence 1 < 2; reformulating.
ACT (attempt 2): query='tell me about db database'
       -> confidence=2, snippets from ['docs/DATABASE.md']
CHECK: confidence 2 >= 2; proceeding to answer.
ANSWER: generated via offline (retrieved snippets).
SELF-CHECK: grounding ratio = 0.91
```

The docs say "database", not "db". The agent detects the weak first result,
expands `db -> database` from its synonym map, and retries successfully. This is
the core agentic behaviour: it checks its own work and acts to improve it.

---

## Trace 3 — Refusal (no supporting evidence -> guardrail fires)

**Question:** Is there any mention of payment processing?

```
PLAN:  generated 1 search query(ies): ['Is there any mention of payment processing?']
ACT (attempt 1): query='Is there any mention of payment processing?'
       -> confidence=0, snippets from none
CHECK: confidence 0 < 2 and no reformulations left.
DECIDE: no supporting snippets found -> refusing.
```

No snippet contains the meaningful query words, so the agent refuses
("I do not know based on the docs I have") instead of guessing.

---

## Live traces (appended automatically on each run)

## 2026-08-04T01:16:45 — Where is the auth token generated?

- Refused: False
- Confidence: 2
- Sources: ['docs/AUTH.md', 'docs/API_REFERENCE.md', 'docs/API_REFERENCE.md']

Reasoning trace:

1. PLAN: generated 2 search query(ies): ['Where is the auth token generated?', 'auth token generated authentication token']
1. ACT (attempt 1): query='Where is the auth token generated?' -> confidence=2, snippets from ['docs/AUTH.md', 'docs/API_REFERENCE.md', 'docs/API_REFERENCE.md']
1. CHECK: confidence 2 >= 2; proceeding to answer.
1. ANSWER: generated via offline (retrieved snippets).
1. SELF-CHECK: grounding ratio = 0.89

---

## 2026-08-04T01:16:45 — What environment variables are required for authentication?

- Refused: False
- Confidence: 4
- Sources: ['docs/AUTH.md', 'docs/SETUP.md', 'docs/AUTH.md']

Reasoning trace:

1. PLAN: generated 1 search query(ies): ['What environment variables are required for authentication?']
1. ACT (attempt 1): query='What environment variables are required for authentication?' -> confidence=4, snippets from ['docs/AUTH.md', 'docs/SETUP.md', 'docs/AUTH.md']
1. CHECK: confidence 4 >= 2; proceeding to answer.
1. ANSWER: generated via offline (retrieved snippets).
1. SELF-CHECK: grounding ratio = 0.89

---

## 2026-08-04T01:16:45 — Which endpoint lists all users?

- Refused: False
- Confidence: 3
- Sources: ['docs/API_REFERENCE.md', 'docs/API_REFERENCE.md', 'docs/DATABASE.md']

Reasoning trace:

1. PLAN: generated 2 search query(ies): ['Which endpoint lists all users?', 'endpoint list all user route']
1. ACT (attempt 1): query='Which endpoint lists all users?' -> confidence=3, snippets from ['docs/API_REFERENCE.md', 'docs/API_REFERENCE.md', 'docs/DATABASE.md']
1. CHECK: confidence 3 >= 2; proceeding to answer.
1. ANSWER: generated via offline (retrieved snippets).
1. SELF-CHECK: grounding ratio = 0.86

---

## 2026-08-04T01:16:45 — How do I connect to the database?

- Refused: False
- Confidence: 3
- Sources: ['docs/DATABASE.md', 'docs/DATABASE.md', 'docs/DATABASE.md']

Reasoning trace:

1. PLAN: generated 2 search query(ies): ['How do I connect to the database?', 'connect database connection database_url']
1. ACT (attempt 1): query='How do I connect to the database?' -> confidence=1, snippets from ['docs/DATABASE.md', 'docs/DATABASE.md', 'docs/DATABASE.md']
1. CHECK: confidence 1 < 2; reformulating.
1. ACT (attempt 2): query='connect database connection database_url' -> confidence=3, snippets from ['docs/DATABASE.md', 'docs/DATABASE.md', 'docs/DATABASE.md']
1. CHECK: confidence 3 >= 2; proceeding to answer.
1. ANSWER: generated via offline (retrieved snippets).
1. SELF-CHECK: grounding ratio = 0.92

---

## 2026-08-04T01:16:45 — Which fields are stored in the users table?

- Refused: False
- Confidence: 1
- Sources: ['docs/API_REFERENCE.md', 'docs/API_REFERENCE.md', 'docs/API_REFERENCE.md']

Reasoning trace:

1. PLAN: generated 1 search query(ies): ['Which fields are stored in the users table?']
1. ACT (attempt 1): query='Which fields are stored in the users table?' -> confidence=1, snippets from ['docs/API_REFERENCE.md', 'docs/API_REFERENCE.md', 'docs/API_REFERENCE.md']
1. CHECK: confidence 1 < 2 and no reformulations left.
1. ANSWER: generated via offline (retrieved snippets).
1. SELF-CHECK: grounding ratio = 0.75

---

## 2026-08-04T01:16:45 — What is the rate limit on public endpoints?

- Refused: False
- Confidence: 4
- Sources: ['knowledge/DEPLOYMENT.md', 'docs/API_REFERENCE.md', 'docs/API_REFERENCE.md']

Reasoning trace:

1. PLAN: generated 2 search query(ies): ['What is the rate limit on public endpoints?', 'rate limit public endpoint route']
1. ACT (attempt 1): query='What is the rate limit on public endpoints?' -> confidence=4, snippets from ['knowledge/DEPLOYMENT.md', 'docs/API_REFERENCE.md', 'docs/API_REFERENCE.md']
1. CHECK: confidence 4 >= 2; proceeding to answer.
1. ANSWER: generated via offline (retrieved snippets).
1. SELF-CHECK: grounding ratio = 0.89

---

## 2026-08-04T01:16:45 — How do I roll back a bad deployment?

- Refused: False
- Confidence: 2
- Sources: ['knowledge/DEPLOYMENT.md', 'docs/SETUP.md', 'knowledge/DEPLOYMENT.md']

Reasoning trace:

1. PLAN: generated 1 search query(ies): ['How do I roll back a bad deployment?']
1. ACT (attempt 1): query='How do I roll back a bad deployment?' -> confidence=2, snippets from ['knowledge/DEPLOYMENT.md', 'docs/SETUP.md', 'knowledge/DEPLOYMENT.md']
1. CHECK: confidence 2 >= 2; proceeding to answer.
1. ANSWER: generated via offline (retrieved snippets).
1. SELF-CHECK: grounding ratio = 0.90

---

## 2026-08-04T01:16:45 — Is there any mention of payment processing?

- Refused: True
- Confidence: 0
- Sources: []

Reasoning trace:

1. PLAN: generated 1 search query(ies): ['Is there any mention of payment processing?']
1. ACT (attempt 1): query='Is there any mention of payment processing?' -> confidence=0, snippets from none
1. CHECK: confidence 0 < 2 and no reformulations left.
1. DECIDE: no supporting snippets found -> refusing.

---

## 2026-08-04T01:16:45 — What is the weather today?

- Refused: True
- Confidence: 0
- Sources: []

Reasoning trace:

1. PLAN: generated 1 search query(ies): ['What is the weather today?']
1. ACT (attempt 1): query='What is the weather today?' -> confidence=0, snippets from none
1. CHECK: confidence 0 < 2 and no reformulations left.
1. DECIDE: no supporting snippets found -> refusing.

---

## 2026-08-04T01:16:45 — How much does the premium subscription cost?

- Refused: True
- Confidence: 0
- Sources: []

Reasoning trace:

1. PLAN: generated 1 search query(ies): ['How much does the premium subscription cost?']
1. ACT (attempt 1): query='How much does the premium subscription cost?' -> confidence=0, snippets from none
1. CHECK: confidence 0 < 2 and no reformulations left.
1. DECIDE: no supporting snippets found -> refusing.

---
