"""
frontend/pages/2_Ask_AI.py — Natural language Q&A interface (RAG).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
from api_client import api_get, api_post, require_case_selected, risk_color

st.set_page_config(page_title="Ask AI — UFDR Platform", page_icon="💬", layout="wide")
st.title("💬 Ask AI About This Case")

case_id = require_case_selected()
if not case_id:
    st.stop()

# Check the case is actually "ready" before allowing a question — the
# backend's POST /ai/{case_id}/ask returns 400 if the case is still
# "processing" (e.g. right after upload, before ChromaDB indexing
# finishes), which previously looked like a silent failure on this page
# with no visible explanation. Surfacing status here makes the cause
# obvious instead of leaving the officer to guess why "Ask" didn't work.
status_check = api_get(f"/upload/case/{case_id}/status")
if status_check and status_check.get("status") != "ready":
    st.warning(
        f"⏳ This case is still **{status_check.get('status', 'processing')}**. "
        "Questions can't be answered until processing finishes — wait a "
        "moment and refresh, or check the Upload & Cases page."
    )
    st.stop()

mode_result = api_get("/ai/mode")
if mode_result:
    mode = mode_result.get("mode", "offline")
    if mode == "gemini":
        st.success("🟢 AI Mode: **Gemini** — answers are AI-generated and evidence-grounded.")
    elif mode == "openai":
        st.success("🟢 AI Mode: **OpenAI** — answers are AI-generated and evidence-grounded.")
    else:
        st.info(
            "🔵 AI Mode: **Offline** — no API key configured, so answers are a "
            "structured list of the most relevant evidence rather than an "
            "AI-written summary. Add `GEMINI_API_KEY` to `.env` for AI-generated answers."
        )

st.caption(
    "Every answer is grounded in retrieved evidence only — the AI is "
    "instructed not to use anything beyond what's shown in the cited "
    "sources below. Nothing here should be taken as a final finding "
    "without verification by a qualified examiner."
)

example_questions = [
    "Is there any evidence of cryptocurrency transactions?",
    "Are there any communications with foreign numbers?",
    "Summarize the most suspicious conversations in this case.",
    "Is there any mention of weapons or explosives?",
]

st.write("**Try an example, or ask your own question:**")
cols = st.columns(len(example_questions))
example_clicked = None
for col, q in zip(cols, example_questions):
    with col:
        if st.button(q, use_container_width=True):
            example_clicked = q

question = st.text_area(
    "Your question",
    value=example_clicked or "",
    placeholder="e.g. Is there any evidence of cryptocurrency transactions?",
    height=80,
)

with st.expander("Advanced options"):
    col1, col2, col3 = st.columns(3)
    with col1:
        record_type = st.selectbox("Limit to record type", ["", "chat", "call", "contact"])
    with col2:
        min_risk = st.slider("Minimum risk score", 0.0, 10.0, 0.0, 0.5, key="ask_min_risk")
    with col3:
        top_k = st.slider("Evidence records to retrieve", 5, 30, 15, key="ask_top_k")

if st.button("🔍 Ask", type="primary", disabled=not question.strip()):
    with st.spinner("Retrieving evidence and generating answer..."):
        result = api_post(
            f"/ai/{case_id}/ask",
            json_body={
                "question": question,
                "record_type": record_type,
                "min_risk": min_risk,
                "top_k": top_k,
            },
        )

    if result:
        if result.get("subquestions") and len(result["subquestions"]) > 1:
            st.caption(
                "🔀 Detected multiple topics — retrieved evidence "
                "separately for each: " + " | ".join(f"*{q}*" for q in result["subquestions"])
            )

        st.subheader("Answer")
        st.write(result["answer"])

        st.caption(
            f"Mode: **{result['mode']}** — based on {result['evidence_count']} "
            f"retrieved evidence record(s)"
        )

        if result.get("sources"):
            with st.expander(f"📎 View {len(result['sources'])} cited source records"):
                for i, src in enumerate(result["sources"], 1):
                    with st.container(border=True):
                        st.write(
                            f"{risk_color(src['risk_score'])} **[{i}] {src['record_type']}** "
                            f"— risk: {src['risk_score']} — `{src['record_id']}`"
                        )
                        st.write(src["text"])