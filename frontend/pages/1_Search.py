"""
frontend/pages/1_Search.py — Keyword + semantic search over the active case.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
from api_client import api_get, api_post, require_case_selected, risk_color

st.set_page_config(page_title="Search — UFDR Platform", page_icon="🔎", layout="wide")
st.title("🔎 Search Evidence")

case_id = require_case_selected()
if not case_id:
    st.stop()

tab_keyword, tab_semantic, tab_prebuilt = st.tabs(
    ["🔤 Keyword Search", "🧠 Semantic Search", "⚡ Pre-built Queries"]
)

# ── Keyword search ───────────────────────────────────────────────────
with tab_keyword:
    st.caption("Exact substring match against message text — fast, no AI needed.")

    col1, col2, col3 = st.columns(3)
    with col1:
        kw_query = st.text_input("Search term", placeholder="e.g. bitcoin, cash, bomb")
    with col2:
        kw_min_risk = st.slider("Minimum risk score", 0.0, 10.0, 0.0, 0.5)
    with col3:
        kw_platform = st.selectbox(
            "Platform", ["", "WhatsApp", "Telegram", "SMS", "Instagram"]
        )

    kw_flagged_only = st.checkbox("Flagged messages only")

    if st.button("Search", key="kw_search_btn", type="primary"):
        results = api_get(
            f"/query/{case_id}/chats/search",
            params={
                "q": kw_query,
                "min_risk": kw_min_risk,
                "platform": kw_platform,
                "flagged_only": kw_flagged_only,
                "limit": 50,
            },
        )
        if results:
            st.write(f"**{results['total_found']} results found**")
            for r in results["results"]:
                with st.container(border=True):
                    st.write(
                        f"{risk_color(r['risk_score'])} **{r['sender']}** → "
                        f"**{r['receiver']}** ({r['platform']}) — risk: {r['risk_score']}"
                    )
                    st.write(r["message"])
                    st.caption(r["timestamp"])

# ── Semantic search ──────────────────────────────────────────────────
with tab_semantic:
    st.caption(
        "Finds records by MEANING, not exact wording — e.g. searching "
        "'crypto payment' can surface 'send BTC' or 'wallet transfer' "
        "even without those exact words."
    )

    sem_query = st.text_input(
        "Describe what you're looking for",
        placeholder="e.g. cryptocurrency transfer, meeting at night, foreign contact",
        key="sem_query_input",
    )
    col1, col2 = st.columns(2)
    with col1:
        sem_record_type = st.selectbox(
            "Record type", ["", "chat", "call", "contact"], key="sem_type"
        )
    with col2:
        sem_n_results = st.slider("Number of results", 5, 30, 10, key="sem_n")

    if st.button("Search by Meaning", key="sem_search_btn", type="primary"):
        result = api_post(
            f"/search/{case_id}/semantic",
            json_body={
                "query": sem_query,
                "record_type": sem_record_type,
                "n_results": sem_n_results,
            },
        )
        if result:
            st.write(f"**{result['total_found']} results found**")
            for r in result["results"]:
                record = r["record"]
                with st.container(border=True):
                    st.write(
                        f"{risk_color(r['risk_score'])} **{r['record_type']}** — "
                        f"similarity: {r['similarity_score']:.2f}, risk: {r['risk_score']}"
                    )
                    if r["record_type"] == "chat":
                        st.write(
                            f"{record.get('sender', '?')} → {record.get('receiver', '?')}: "
                            f"{record.get('message', '')}"
                        )
                    elif r["record_type"] == "call":
                        st.write(
                            f"{record.get('caller', '?')} → {record.get('receiver', '?')} "
                            f"({record.get('call_type', '?')}, "
                            f"{record.get('duration_seconds', 0)}s)"
                        )
                    elif r["record_type"] == "contact":
                        st.write(f"{record.get('name', '?')} — {record.get('phone_numbers', [])}")
                    else:
                        st.write(r["matched_text"])

# ── Pre-built queries ─────────────────────────────────────────────────
with tab_prebuilt:
    st.caption("Common investigative queries, one click away.")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💰 Show all crypto-related chats", use_container_width=True):
            result = api_get(f"/query/{case_id}/chats/crypto")
            if result:
                st.write(f"**{result['total_found']} crypto-related messages**")
                for r in result["results"]:
                    with st.container(border=True):
                        st.write(f"🔴 **{r['sender']}** → **{r['receiver']}** (risk: {r['risk_score']})")
                        st.write(r["message"])
                        st.caption(f"Addresses: {', '.join(r['crypto_addresses'])}")

    with col2:
        if st.button("🌍 Show all foreign calls", use_container_width=True):
            result = api_get(f"/query/{case_id}/calls/foreign")
            if result:
                st.write(f"**{result['total_found']} foreign calls**")
                for r in result["results"]:
                    with st.container(border=True):
                        st.write(
                            f"{risk_color(r['risk_score'])} **{r['caller']}** → "
                            f"**{r['receiver']}** ({r['call_type']}, "
                            f"{r['duration_minutes']} min, {r['platform']})"
                        )
                        st.caption(r["timestamp"])

    st.divider()
    st.write("**Find common contacts between two numbers**")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        number_a = st.text_input("Number A", placeholder="+919876543210")
    with col2:
        number_b = st.text_input("Number B", placeholder="+919988776655")
    with col3:
        st.write("")
        st.write("")
        common_btn = st.button("Find Common")

    if common_btn and number_a and number_b:
        result = api_get(
            f"/query/{case_id}/contacts/common",
            params={"number_a": number_a, "number_b": number_b},
        )
        if result:
            if result["common_count"] > 0:
                st.success(f"Found {result['common_count']} common contact(s):")
                for c in result["common_contacts"]:
                    st.write(f"- {c}")
            else:
                st.info("No common contacts found between these two numbers.")