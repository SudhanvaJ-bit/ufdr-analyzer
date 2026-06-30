"""
frontend/pages/0_Case_Summary.py — Aggregate case statistics overview.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
from api_client import api_get, require_case_selected, risk_color

st.set_page_config(page_title="Case Summary — UFDR Platform", page_icon="📊", layout="wide")
st.title("📊 Case Summary")

case_id = require_case_selected()
if not case_id:
    st.stop()

result = api_get(f"/query/{case_id}/summary")

if result:
    summary = result["summary"]

    st.subheader("Record Counts")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💬 Chats", summary["chats"]["total"])
    col2.metric("📞 Calls", summary["calls"]["total"])
    col3.metric("👤 Contacts", summary["contacts"]["total"])
    col4.metric("🖼️ Media", summary["media"]["total"])

    st.subheader("Risk Breakdown")
    col1, col2, col3 = st.columns(3)
    col1.metric("🚩 Flagged messages", summary["chats"]["flagged"])
    col2.metric("🔴 High-risk messages", summary["chats"]["high_risk"])
    col3.metric("🌍 Foreign calls", summary["calls"]["foreign"])

    st.divider()
    st.subheader("Top 5 Highest-Risk Messages")
    for msg in result["top_risk_messages"]:
        with st.container(border=True):
            st.write(f"{risk_color(msg['risk_score'])} **{msg['sender']}** — risk: {msg['risk_score']}")
            st.write(msg["message_preview"])

    st.divider()
    st.info(
        "💡 Use the sidebar to explore **Search**, **Ask AI**, "
        "**Link Analysis**, and **Risk Ranking** for this case."
    )