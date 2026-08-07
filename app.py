"""
Streamlit web UI for DocuBot.

A browser front-end over the same core logic used by the CLI: it calls
DocuBot's retrieval, RAG, and agentic workflow directly — no logic is
duplicated here. Run it with:

    streamlit run app.py

Works with or without a GEMINI_API_KEY (RAG/agentic use the LLM when a key is
present; otherwise they fall back to retrieval / the offline agent).
"""

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from docubot import DocuBot
from agent import DocuBotAgent

EXTRA_DOC_FOLDERS = ["knowledge"]


@st.cache_resource
def load_bot():
    """Build DocuBot once and reuse it across interactions (cached)."""
    try:
        from llm_client import GeminiClient
        llm_client = GeminiClient()
        has_llm = True
    except Exception:
        llm_client = None
        has_llm = False
    bot = DocuBot(llm_client=llm_client, extra_folders=EXTRA_DOC_FOLDERS)
    agent = DocuBotAgent(bot, llm_client=llm_client)
    return bot, agent, has_llm


bot, agent, has_llm = load_bot()

st.set_page_config(page_title="DocuBot", page_icon="📄")
st.title("📄 DocuBot")
st.caption("A grounded documentation assistant — answers only from the docs, "
           "and refuses when the answer isn't there.")

# --- Sidebar controls ---
with st.sidebar:
    st.header("Settings")
    mode_options = ["Retrieval only", "RAG", "Agentic"]
    if not has_llm:
        st.warning("No GEMINI_API_KEY found — RAG & Agentic fall back to "
                   "retrieval / offline mode.")
    mode = st.radio("Mode", mode_options, index=1)
    top_k = st.slider("Snippets to retrieve (top_k)", 1, 5, 3)

    st.divider()
    st.subheader("Loaded sources")
    files = sorted({f for f, _ in bot.documents})
    for f in files:
        st.write(f"• `{f}`")

    st.divider()
    st.caption("Try: *Where is the auth token generated?* · "
               "*What is the rate limit on public endpoints?* · "
               "*Is there any mention of payment processing?*")

# --- Main question box ---
query = st.text_input("Ask a question about the docs:",
                      placeholder="e.g. Where is the auth token generated?")

if st.button("Ask", type="primary") and query.strip():
    with st.spinner("Thinking…"):
        if mode == "Retrieval only":
            answer = bot.answer_retrieval_only(query, top_k=top_k)
            st.subheader("Retrieved snippets")
            st.markdown(answer)

        elif mode == "RAG":
            if has_llm:
                answer = bot.answer_rag(query, top_k=top_k)
            else:
                answer = bot.answer_retrieval_only(query, top_k=top_k)
            st.subheader("Answer")
            st.markdown(answer)

        else:  # Agentic
            result = agent.run(query, top_k=top_k)
            st.subheader("Answer")
            st.markdown(result["answer"])
            if result["refused"]:
                st.info("🛡️ Refused — no supporting evidence in the docs.")
            with st.expander("🔎 Reasoning trace (plan → act → check → answer)"):
                for step in result["trace"]:
                    st.write(f"- {step}")
            st.caption(f"Confidence: {result['confidence']} · "
                       f"Sources: {result['snippets'] or 'none'}")
