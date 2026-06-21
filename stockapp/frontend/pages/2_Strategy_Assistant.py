"""
RAG Assistant page.

Lets the user ask questions about:
  - RSI / swing trading strategy concepts (from the static knowledge base)
  - Their own stored stocks (RSI, price, buy range) — pulled live from SQLite at query time
Answers are generated via a local Ollama model if available, otherwise falls back
to showing the raw retrieved context.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from frontend import api_client as api

st.set_page_config(page_title="Strategy Assistant", page_icon="🤖", layout="wide")
st.title("🤖 Swing Trading Strategy Assistant (RAG)")
st.caption("Ask about RSI strategy concepts, or about specific stocks on your watchlist.")

if not api.health_check():
    st.error("⚠️ Backend API not reachable. Start it with: `uvicorn backend.main:app --reload --port 8000`")
    st.stop()

with st.expander("ℹ️ What can I ask?"):
    st.markdown(
        "- *Why do we buy when RSI is below 40?*\n"
        "- *What does RSI above 70 mean?*\n"
        "- *What is the RSI for [stock name] right now?*\n"
        "- *Is [stock name] in my buy price range?*\n"
        "- *What's the difference between BUY, WATCH, and HOLD signals?*\n"
        "- *Why use a buy price range instead of one price?*"
    )

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            st.caption("📚 Sources: " + ", ".join(msg["sources"]))

question = st.chat_input("Ask about your strategy or a stock on your watchlist...")

if question:
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving context and generating answer..."):
            try:
                result = api.rag_query(question)
                answer = result["answer"]
                sources = result.get("sources", [])
                mode = result.get("mode", "")

                st.markdown(answer)
                if sources:
                    st.caption("📚 Sources: " + ", ".join(sources))
                if mode == "retrieval_only":
                    st.info("ℹ️ Local LLM (Ollama) not detected — showing retrieved notes directly. "
                             "Install Ollama and run `ollama pull llama3.2` for generated answers.")

                st.session_state.chat_history.append(
                    {"role": "assistant", "content": answer, "sources": sources}
                )
            except Exception as e:
                err_msg = f"Sorry, something went wrong: {e}"
                st.error(err_msg)
                st.session_state.chat_history.append({"role": "assistant", "content": err_msg})

if st.session_state.chat_history:
    if st.button("🗑️ Clear conversation"):
        st.session_state.chat_history = []
        st.rerun()
