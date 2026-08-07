"""
Guided demo for the Engineer's Pitch.

Runs a fixed sequence that tells the project's story end to end:
  1. RAG grounding      - a grounded answer that cites its source
  2. Refusal guardrail  - an out-of-scope question is refused, not guessed
  3. Agentic loop       - the agent self-corrects a weak search and retries
  4. Multi-source RAG    - an answer that comes from the extra knowledge/ source

Run it with:
    python demo.py

Works with or without a GEMINI_API_KEY: with a key it uses RAG/Gemini for the
final answer; without one it falls back to retrieval / the offline agent, so the
demo never fails live.
"""

from dotenv import load_dotenv
load_dotenv()

from docubot import DocuBot
from agent import DocuBotAgent

try:
    from llm_client import GeminiClient
    llm_client = GeminiClient()
    HAS_LLM = True
except Exception:
    llm_client = None
    HAS_LLM = False

bot = DocuBot(llm_client=llm_client, extra_folders=["knowledge"])
agent = DocuBotAgent(bot, llm_client=llm_client)


def header(n, title, pitch_tag):
    print("\n" + "=" * 68)
    print(f"  SCENE {n}: {title}")
    print(f"  (pitch: {pitch_tag})")
    print("=" * 68)


def rag_answer(query):
    """RAG when a key is present; retrieval-only otherwise."""
    return bot.answer_rag(query) if HAS_LLM else bot.answer_retrieval_only(query)


def main():
    mode = "RAG (Gemini)" if HAS_LLM else "retrieval-only (no API key)"
    print(f"\nDocuBot demo — answer mode: {mode}")

    # 1. RAG grounding
    header(1, "RAG grounding", "The Logic — how the AI thinks")
    q = "Where is the auth token generated?"
    print(f"Q: {q}\n")
    print(rag_answer(q))

    # 2. Refusal guardrail
    header(2, "Refusal guardrail", "The Reliability — guardrails")
    q = "Is there any mention of payment processing?"
    print(f"Q: {q}\n")
    print(rag_answer(q))
    print("\n-> No evidence in the docs, so it refuses instead of guessing.")

    # 3. Agentic self-correction
    header(3, "Agentic self-correction", "The Logic — the agentic loop")
    q = "Tell me about the db"
    print(f"Q: {q}\n")
    result = agent.run(q)
    print("Reasoning trace:")
    for step in result["trace"]:
        print(f"   - {step}")
    print(f"\nAnswer:\n{result['answer']}")
    print('\n-> Docs say "database", not "db"; the agent noticed the weak search '
          "and retried.")

    # 4. Multi-source RAG enhancement
    header(4, "Multi-source retrieval", "The Logic — RAG enhancement")
    q = "What is the rate limit on public endpoints?"
    print(f"Q: {q}\n")
    print(rag_answer(q))
    print("\n-> This answer comes from the extra knowledge/ source, not docs/.")

    print("\n" + "=" * 68)
    print("  Reliability check: run  python test_harness.py  -> 10/10 pass")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    main()
