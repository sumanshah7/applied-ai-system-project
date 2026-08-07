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

EXAMPLES = [
    "Where is the auth token generated?",
    "What is the rate limit on public endpoints?",
    "Is there any mention of payment processing?",
    "Tell me about the db",
]


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


def answer_query(bot, agent, has_llm, query, mode, top_k):
    """Route a query to the chosen mode and return a uniform result dict."""
    scored = bot.retrieve_scored(query, top_k=top_k)
    sources, seen = [], set()
    for _, f, _ in scored:
        if f not in seen:
            seen.add(f)
            sources.append(f)
    confidence = scored[0][0] if scored else 0

    if mode == "Retrieval only":
        answer = bot.answer_retrieval_only(query, top_k=top_k)
        return {"answer": answer, "confidence": confidence, "sources": sources,
                "trace": None, "refused": not scored}

    if mode == "RAG":
        answer = (bot.answer_rag(query, top_k=top_k) if has_llm
                  else bot.answer_retrieval_only(query, top_k=top_k))
        return {"answer": answer, "confidence": confidence, "sources": sources,
                "trace": None, "refused": "do not know" in answer.lower()}

    # Agentic
    result = agent.run(query, top_k=top_k)
    return {"answer": result["answer"], "confidence": result["confidence"],
            "sources": result["snippets"], "trace": result["trace"],
            "refused": result["refused"]}


def render_meta(msg):
    """Render badges, sources, and (for agentic) the reasoning trace."""
    if msg.get("refused"):
        st.info("🛡️ Refused — no supporting evidence in the docs.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Mode", msg["mode"])
    c2.metric("Confidence", msg["confidence"])
    c3.metric("Sources", len(msg["sources"]))

    if msg["sources"]:
        st.markdown("**Sources:** " + "  ".join(f"`{s}`" for s in msg["sources"]))

    if msg.get("trace"):
        with st.expander("🔎 Reasoning trace  ·  plan → act → check → answer"):
            for step in msg["trace"]:
                st.write(f"- {step}")


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="DocuBot", page_icon="📄", layout="centered")

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.5rem;}
      div[data-testid="stMetric"] {background:#f6f7f9; border-radius:10px;
          padding:8px 12px;}
      @media (prefers-color-scheme: dark){
          div[data-testid="stMetric"] {background:#1e222a;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)

bot, agent, has_llm = load_bot()

st.title("📄 DocuBot")
st.caption("A grounded documentation assistant — it answers only from your docs, "
           "cites its sources, and refuses when the answer isn't there.")

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")
    if has_llm:
        st.success("Gemini connected — RAG & Agentic use the LLM.")
    else:
        st.warning("No GEMINI_API_KEY — RAG & Agentic fall back to retrieval.")

    mode = st.radio(
        "Answer mode",
        ["Retrieval only", "RAG", "Agentic"],
        index=1,
        captions=["Snippets only, no LLM",
                  "Retrieve, then answer from snippets",
                  "Plan → search → self-check → retry"],
    )
    top_k = st.slider("Snippets to retrieve (top_k)", 1, 5, 3)

    st.divider()
    st.subheader("💡 Try an example")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True, key=f"ex_{ex}"):
            st.session_state.pending = ex

    st.divider()
    st.subheader("📚 Loaded sources")
    for f in sorted({f for f, _ in bot.documents}):
        st.write(f"• `{f}`")

    st.divider()
    if st.button("🧹 Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            render_meta(msg)

# ---------------------------------------------------------------------------
# Input (chat box or an example button)
# ---------------------------------------------------------------------------
prompt = st.chat_input("Ask a question about the docs…")
if not prompt and "pending" in st.session_state:
    prompt = st.session_state.pop("pending")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            res = answer_query(bot, agent, has_llm, prompt, mode, top_k)
        st.markdown(res["answer"])
        entry = {"role": "assistant", "content": res["answer"], "mode": mode,
                 "confidence": res["confidence"], "sources": res["sources"],
                 "trace": res["trace"], "refused": res["refused"]}
        render_meta(entry)
        st.session_state.messages.append(entry)
