"""
graph_analyzer.py — Link analysis: builds a communication graph from a
case's chats and calls, and computes centrality metrics to surface key
people in a suspect network.

WHY THIS FILE EXISTS:
  query.py's find_common_contacts() answers a narrow question ("did these
  two specific numbers both talk to some third number?"). This module
  answers a broader one: "across this entire case, who are the most
  important people in the communication network, and how are they
  connected?" That's a fundamentally different kind of question — it
  needs a graph, not a single SQL query.

GRAPH DESIGN:
  - Nodes = phone numbers (from both chats and calls).
  - Edges = combined chat + call activity between two numbers, in ONE
    undirected weighted edge per pair (direction of who-contacted-whom
    is interesting but secondary to "do these two people have a
    relationship at all" for a first-pass link analysis).
  - Edge weight = a combination of how OFTEN two people communicated and
    how RISKY those communications were — two numbers that exchanged 20
    bland messages should not outrank two numbers that exchanged 2
    crypto-address messages. See _edge_weight() for the exact formula.

CENTRALITY METRICS COMPUTED:
  - Degree centrality: how many distinct people does this number talk
    to? High degree = a "hub" — often an organizer or distributor.
  - Betweenness centrality: how often does this number sit on the
    shortest path between two OTHER people who aren't directly
    connected? High betweenness = a "bridge" or "broker" — frequently
    the most operationally important person in a network even if they
    aren't the most talkative one, since removing them would disconnect
    otherwise-separate groups.
  - Weighted degree (sum of edge weights): a quick "how much
    high-risk/high-volume activity touches this number" signal.

INTERVIEW EXPLANATION:
  "I build an undirected weighted graph where nodes are phone numbers and
  edges combine chat and call activity between them, weighted by both
  frequency and the risk score of the underlying messages. Then I compute
  degree and betweenness centrality — degree finds the most-contacted
  hubs, betweenness finds the people who bridge otherwise-separate
  groups, which is often the more interesting investigative lead even
  when that person doesn't have the most messages."
"""

import networkx as nx
from collections import defaultdict


def _edge_weight(count: int, total_risk: float) -> float:
    """
    Combine communication frequency and cumulative risk into one edge
    weight. Frequency alone would let 20 bland "kal subah aaunga"
    messages outrank 2 messages containing a crypto address — that's
    backwards for an investigator's purposes, so risk gets a heavier
    multiplier than raw count.
    """
    return count + (total_risk * 2)


def build_communication_graph(chats: list, calls: list) -> nx.Graph:
    """
    Build one undirected weighted graph combining chat and call activity.

    Each ChatMessage/CallRecord contributes to the edge between its two
    participants. Multiple records between the same pair accumulate into
    a single edge, tracking:
      - chat_count / call_count (so the breakdown is visible, not just
        a single opaque weight)
      - total_risk (sum of risk_score across all records on this edge)
      - max_risk (the single riskiest record on this edge — useful for
        flagging "this pair had at least one high-risk message" even if
        most of their traffic was mundane)

    Args:
        chats: list of ChatMessage ORM objects (or dicts with the same fields)
        calls: list of CallRecord ORM objects (or dicts with the same fields)

    Returns:
        networkx.Graph with node attribute "label" and edge attributes
        {chat_count, call_count, total_risk, max_risk, weight}.
    """
    # Accumulate raw stats per (numberA, numberB) pair before building
    # the graph, so each pair becomes exactly one edge regardless of how
    # many individual records connect them.
    pair_stats = defaultdict(lambda: {
        "chat_count": 0, "call_count": 0, "total_risk": 0.0, "max_risk": 0.0
    })

    def _pair_key(a: str, b: str) -> tuple:
        # Undirected: sort so (A, B) and (B, A) land on the same key.
        return tuple(sorted((a or "Unknown", b or "Unknown")))

    for chat in chats:
        sender = getattr(chat, "sender", None)
        receiver = getattr(chat, "receiver", None)
        risk = getattr(chat, "risk_score", 0.0) or 0.0
        if not sender or not receiver or sender == receiver:
            continue  # skip malformed/self records — not a real edge
        key = _pair_key(sender, receiver)
        pair_stats[key]["chat_count"] += 1
        pair_stats[key]["total_risk"] += risk
        pair_stats[key]["max_risk"] = max(pair_stats[key]["max_risk"], risk)

    for call in calls:
        caller = getattr(call, "caller_number", None)
        receiver = getattr(call, "receiver_number", None)
        risk = getattr(call, "risk_score", 0.0) or 0.0
        if not caller or not receiver or caller == receiver:
            continue
        key = _pair_key(caller, receiver)
        pair_stats[key]["call_count"] += 1
        pair_stats[key]["total_risk"] += risk
        pair_stats[key]["max_risk"] = max(pair_stats[key]["max_risk"], risk)

    graph = nx.Graph()
    for (a, b), stats in pair_stats.items():
        total_count = stats["chat_count"] + stats["call_count"]
        weight = _edge_weight(total_count, stats["total_risk"])
        graph.add_node(a, label=a)
        graph.add_node(b, label=b)
        graph.add_edge(
            a, b,
            chat_count=stats["chat_count"],
            call_count=stats["call_count"],
            total_risk=round(stats["total_risk"], 2),
            max_risk=round(stats["max_risk"], 2),
            weight=round(weight, 2),
        )

    return graph


def compute_centrality(graph: nx.Graph) -> dict:
    """
    Compute degree and betweenness centrality for every node, plus
    weighted degree (sum of incident edge weights).

    Returns a dict keyed by phone number:
      {
        "<number>": {
          "degree_centrality": float (0-1, normalized),
          "betweenness_centrality": float (0-1, normalized),
          "weighted_degree": float,
          "connections": int,
        },
        ...
      }

    NOTE ON SCALE: NetworkX's betweenness_centrality is O(V*E) — fine for
    a single case's contact graph (dozens to low hundreds of nodes), but
    would need approximation (e.g. the `k` sampling parameter) for a
    graph spanning many large cases merged together.
    """
    if graph.number_of_nodes() == 0:
        return {}

    degree_c = nx.degree_centrality(graph)
    betweenness_c = nx.betweenness_centrality(graph, weight="weight")

    result = {}
    for node in graph.nodes():
        weighted_degree = sum(
            data.get("weight", 0) for _, _, data in graph.edges(node, data=True)
        )
        result[node] = {
            "degree_centrality": round(degree_c.get(node, 0.0), 4),
            "betweenness_centrality": round(betweenness_c.get(node, 0.0), 4),
            "weighted_degree": round(weighted_degree, 2),
            "connections": graph.degree(node),
        }
    return result


def graph_to_json(graph: nx.Graph, centrality: dict) -> dict:
    """
    Serialize the graph + centrality scores into a frontend-ready JSON
    shape: a flat nodes list and edges list, which is what graph
    visualization libraries (react-force-graph, Pyvis, vis-network)
    expect rather than NetworkX's native object.
    """
    nodes = [
        {
            "id": node,
            "label": node,
            **centrality.get(node, {
                "degree_centrality": 0.0,
                "betweenness_centrality": 0.0,
                "weighted_degree": 0.0,
                "connections": 0,
            }),
        }
        for node in graph.nodes()
    ]

    edges = [
        {
            "source": a,
            "target": b,
            "chat_count": data.get("chat_count", 0),
            "call_count": data.get("call_count", 0),
            "total_risk": data.get("total_risk", 0.0),
            "max_risk": data.get("max_risk", 0.0),
            "weight": data.get("weight", 0.0),
        }
        for a, b, data in graph.edges(data=True)
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }


def get_top_connectors(centrality: dict, top_n: int = 5) -> list:
    """
    Return the top_n numbers ranked by betweenness centrality — i.e. the
    people who most frequently bridge otherwise-separate parts of the
    network. Often a more useful investigative lead than "who has the
    most messages," since a bridge can be a low-volume coordinator
    rather than a high-volume chatter.

    NOTE: nodes with betweenness_centrality == 0 are excluded entirely,
    even if that means returning fewer than top_n results. A score of 0
    means "not a bridge at all" (every pair this node touches can also
    reach each other without it) — not "a weak bridge." Including them
    just to fill the list would misleadingly suggest they have some
    bridging role when they structurally don't. This came up directly
    while validating against real sample data: a high-degree hub that
    talks to everyone had betweenness 0, and without this filter it would
    have shown up in the "bridges" list purely because the list needed
    padding, not because it bridges anything.
    """
    bridges_only = [
        (number, scores)
        for number, scores in centrality.items()
        if scores["betweenness_centrality"] > 0
    ]
    ranked = sorted(
        bridges_only,
        key=lambda kv: kv[1]["betweenness_centrality"],
        reverse=True,
    )
    return [
        {"number": number, **scores}
        for number, scores in ranked[:top_n]
    ]


def get_top_hubs(centrality: dict, top_n: int = 5) -> list:
    """
    Return the top_n numbers ranked by degree centrality — the most
    widely-connected people in the network (talks to the most distinct
    others), regardless of how "important" any single connection is.
    """
    ranked = sorted(
        centrality.items(),
        key=lambda kv: kv[1]["degree_centrality"],
        reverse=True,
    )
    return [
        {"number": number, **scores}
        for number, scores in ranked[:top_n]
    ]