"""
routers/analysis.py — Link analysis endpoints (Phase 8).

WHY A SEPARATE ROUTER FROM query.py?
  query.py's /contacts/common already does a narrow, single-pair version
  of link analysis ("did these two specific numbers share a contact?").
  This router answers the case-wide version: "across everyone in this
  case, who are the key people, and how is the whole network connected?"
  That needs the full graph, not a single SQL query, so it gets its own
  module (graph_analyzer.py) and its own router.

ENDPOINTS IN THIS FILE:
  GET /analysis/{case_id}/graph        — full graph as nodes+edges JSON,
                                          ready for a frontend graph view.
  GET /analysis/{case_id}/key-players   — top hubs (degree) and top
                                          bridges (betweenness) in one
                                          response, the quick "who matters
                                          here" answer for an officer.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Case, ChatMessage, CallRecord
from backend.analysis.graph_analyzer import (
    build_communication_graph,
    compute_centrality,
    graph_to_json,
    get_top_connectors,
    get_top_hubs,
)

router = APIRouter(prefix="/analysis", tags=["Link Analysis"])


def _require_case(case_id: str, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _build_graph_for_case(case_id: str, db: Session):
    """Shared helper: load this case's chats+calls and build the graph."""
    chats = db.query(ChatMessage).filter(ChatMessage.case_id == case_id).all()
    calls = db.query(CallRecord).filter(CallRecord.case_id == case_id).all()
    graph = build_communication_graph(chats, calls)
    centrality = compute_centrality(graph)
    return graph, centrality


@router.get("/{case_id}/graph")
def get_communication_graph(case_id: str, db: Session = Depends(get_db)):
    """
    Return the full communication graph for this case as nodes + edges,
    with degree/betweenness centrality already computed per node.

    Designed to be consumed directly by a graph visualization library
    (react-force-graph, vis-network, Pyvis) without further processing.
    """
    _require_case(case_id, db)

    graph, centrality = _build_graph_for_case(case_id, db)

    if graph.number_of_nodes() == 0:
        return {
            "case_id": case_id,
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "message": "No chat or call records with valid sender/receiver "
                       "numbers were found for this case.",
        }

    result = graph_to_json(graph, centrality)
    return {"case_id": case_id, **result}


@router.get("/{case_id}/key-players")
def get_key_players(
    case_id: str,
    top_n: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Quick answer to "who matters in this case's communication network?"

    Returns two ranked lists:
      - hubs: highest degree centrality — most widely-connected numbers.
      - bridges: highest betweenness centrality — numbers that connect
        otherwise-separate groups. Often the more useful investigative
        lead, since a low-volume coordinator can bridge two cells
        without being the most talkative person in either one.
    """
    _require_case(case_id, db)

    graph, centrality = _build_graph_for_case(case_id, db)

    if not centrality:
        return {
            "case_id": case_id,
            "hubs": [],
            "bridges": [],
            "message": "No communication graph could be built for this case.",
        }

    return {
        "case_id": case_id,
        "total_people": graph.number_of_nodes(),
        "total_connections": graph.number_of_edges(),
        "hubs": get_top_hubs(centrality, top_n=top_n),
        "bridges": get_top_connectors(centrality, top_n=top_n),
        "note": (
            "'bridges' only includes nodes with nonzero betweenness "
            "centrality — a node that connects to everyone directly can "
            "be a major hub while still not bridging anything, so it may "
            "be intentionally absent here even if it appears in 'hubs'."
        ),
    }