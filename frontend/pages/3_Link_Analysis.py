"""
frontend/pages/3_Link_Analysis.py — Visual communication graph (Pyvis)
plus key-players summary, backed by Phase 8's backend/analysis/graph_analyzer.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network
from api_client import api_get, require_case_selected

st.set_page_config(page_title="Link Analysis — UFDR Platform", page_icon="🕸️", layout="wide")
st.title("🕸️ Link Analysis — Communication Network")

case_id = require_case_selected()
if not case_id:
    st.stop()

st.caption(
    "Nodes are phone numbers. Node **size** reflects how many people they "
    "talk to (degree centrality) — bigger means more connected. Node "
    "**color** reflects betweenness centrality — redder means they bridge "
    "otherwise-separate groups, which is often a more important lead than "
    "raw popularity. Edge thickness reflects communication frequency + risk."
)


def _betweenness_color(score: float) -> str:
    """Map betweenness centrality (0-1) to a color scale from blue
    (no bridging role) to red (strong bridge)."""
    if score == 0:
        return "#4287f5"   # blue — not a bridge at all
    elif score < 0.2:
        return "#f5a742"   # amber — weak bridge
    elif score < 0.5:
        return "#f57842"   # orange — moderate bridge
    else:
        return "#e63946"   # red — strong bridge


def build_pyvis_graph(graph_data: dict) -> str:
    """Convert the backend's nodes+edges JSON into a Pyvis network and
    return its rendered HTML, ready for embedding via components.html."""
    net = Network(
        height="600px", width="100%", bgcolor="#0e1117", font_color="white",
        directed=False,
    )
    net.barnes_hut(spring_length=150, spring_strength=0.02, damping=0.5)

    for node in graph_data["nodes"]:
        degree_c = node["degree_centrality"]
        betweenness_c = node["betweenness_centrality"]
        size = 15 + (degree_c * 35)  # scale 15-50px by degree centrality
        net.add_node(
            node["id"],
            label=node["id"],
            size=size,
            color=_betweenness_color(betweenness_c),
            title=(
                f"{node['id']}\n"
                f"Connections: {node['connections']}\n"
                f"Degree centrality: {degree_c:.3f}\n"
                f"Betweenness centrality: {betweenness_c:.3f}\n"
                f"Weighted degree: {node['weighted_degree']}"
            ),
        )

    for edge in graph_data["edges"]:
        width = 1 + min(edge["weight"] / 10, 8)  # cap so one huge edge doesn't dominate
        net.add_edge(
            edge["source"],
            edge["target"],
            value=width,
            title=(
                f"Chats: {edge['chat_count']}, Calls: {edge['call_count']}\n"
                f"Total risk: {edge['total_risk']}, Max risk: {edge['max_risk']}"
            ),
        )

    return net.generate_html()


graph_data = api_get(f"/analysis/{case_id}/graph")

if graph_data and graph_data.get("node_count", 0) > 0:
    col1, col2, col3 = st.columns(3)
    col1.metric("People in network", graph_data["node_count"])
    col2.metric("Connections", graph_data["edge_count"])
    col3.metric("Network density", f"{graph_data['edge_count'] / max(graph_data['node_count'], 1):.1f} edges/node")

    html = build_pyvis_graph(graph_data)
    components.html(html, height=620, scrolling=False)

    st.divider()

    st.subheader("Key Players")
    key_players = api_get(f"/analysis/{case_id}/key-players", params={"top_n": 5})

    if key_players:
        col_hubs, col_bridges = st.columns(2)

        with col_hubs:
            st.write("**🌟 Top Hubs** (most widely connected)")
            for h in key_players["hubs"]:
                st.write(
                    f"- `{h['number']}` — degree: {h['degree_centrality']:.2f}, "
                    f"connections: {h['connections']}"
                )

        with col_bridges:
            st.write("**🌉 Top Bridges** (connect otherwise-separate groups)")
            if key_players["bridges"]:
                for b in key_players["bridges"]:
                    st.write(
                        f"- `{b['number']}` — betweenness: {b['betweenness_centrality']:.3f}"
                    )
            else:
                st.info("No bridges found — every node connects to every other directly.")

        if key_players.get("note"):
            st.caption(key_players["note"])

elif graph_data:
    st.info(
        graph_data.get(
            "message",
            "No communication graph could be built for this case — check "
            "that it has chat or call records with valid sender/receiver numbers.",
        )
    )