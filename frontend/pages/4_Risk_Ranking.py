"""
frontend/pages/4_Risk_Ranking.py — Per-contact combined risk ranking (Phase 9).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
from api_client import api_get, require_case_selected, risk_color

st.set_page_config(page_title="Risk Ranking — UFDR Platform", page_icon="⚠️", layout="wide")
st.title("⚠️ Risk Ranking — Key Investigative Leads")

case_id = require_case_selected()
if not case_id:
    st.stop()

top_n = st.slider("Number of contacts to rank", 5, 50, 10)

result = api_get(f"/analysis/{case_id}/risk-ranking", params={"top_n": top_n})

if not result or not result.get("ranking"):
    st.info(
        result.get("message", "No contacts could be scored for this case.")
        if result else "Could not load risk ranking."
    )
    st.stop()

with st.expander("ℹ️ How is this score calculated?"):
    st.write(result["scoring_method"])
    st.caption(
        "This is a transparent, rule-based score — not a black-box model. "
        "Every result below shows its full breakdown so 'why was this "
        "person flagged?' always has a real, inspectable answer."
    )

ranking = result["ranking"]

if len(ranking) >= 2:
    top_score = ranking[0]["combined_score"]
    close_count = sum(1 for r in ranking if top_score - r["combined_score"] <= 0.5)
    if close_count >= 2:
        st.warning(
            f"⚖️ The top {close_count} scores are within 0.5 points of each "
            "other — treat them as a tied cluster of priority leads rather "
            "than a strict 1st/2nd/3rd ordering. Small score gaps reflect "
            "the data's actual signal strength, not a precise ranking."
        )

st.divider()

flag_labels = {
    "bridges_clusters": "🌉 Bridges clusters",
    "foreign_contact": "🌍 Foreign contact",
    "high_risk_content": "🔴 High-risk content",
    "high_network_volume": "📈 High network volume",
}

for i, contact in enumerate(ranking, 1):
    breakdown = contact["breakdown"]
    flags = contact["flags"]
    active_flags = [label for key, label in flag_labels.items() if flags.get(key)]

    with st.container(border=True):
        col_rank, col_main, col_score = st.columns([0.5, 3, 1])

        with col_rank:
            st.write(f"### #{i}")

        with col_main:
            st.write(f"**`{contact['number']}`**")
            if active_flags:
                st.write(" • ".join(active_flags))
            else:
                st.caption("No pattern flags triggered")

        with col_score:
            st.metric("Risk Score", f"{contact['combined_score']:.1f} / 10")

        with st.expander("View full breakdown"):
            b1, b2, b3, b4 = st.columns(4)
            b1.write(f"**Avg content risk**\n\n{breakdown['avg_content_risk']:.2f}")
            b2.write(f"**Peak content risk**\n\n{breakdown['max_content_risk']:.2f}")
            b3.write(f"**Betweenness**\n\n{breakdown['betweenness_centrality']:.3f}")
            b4.write(f"**Weighted degree**\n\n{breakdown['weighted_degree']:.1f}")
            st.caption(f"Based on {breakdown['message_count']} messages involving this contact.")