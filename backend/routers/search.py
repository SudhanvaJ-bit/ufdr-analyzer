"""
routers/search.py — Semantic search endpoints using ChromaDB.

WHY A SEPARATE ROUTER?
  Phase 1's query.py handles SQL-based keyword search.
  This file handles VECTOR-based semantic search.
  Keeping them separate makes the code clean and understandable.
  Both work independently — if Chroma fails, SQL search still works.

ENDPOINTS IN THIS FILE:
  POST /search/{case_id}/semantic     — Main semantic search
  POST /search/{case_id}/ask          — Simple NL question (no LLM yet, Phase 3 adds Gemini)
  GET  /search/{case_id}/similar/{id} — Find records similar to a specific message
  GET  /search/{case_id}/index-status — Check how many docs are indexed
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db
from backend.models import Case, ChatMessage, CallRecord, Contact
from backend.vector_store.chroma_store import get_vector_store
from backend.config import settings

router = APIRouter(prefix="/search", tags=["Semantic Search"])


# ── Request/Response Models ────────────────────────────────────

class SemanticSearchRequest(BaseModel):
    """Body for semantic search POST request."""
    query: str
    record_type: str = ""          # "chat", "call", "contact", or "" for all
    min_risk: float = 0.0
    n_results: int = 15

    class Config:
        json_schema_extra = {
            "example": {
                "query": "messages about cryptocurrency transfers",
                "record_type": "chat",
                "min_risk": 0.0,
                "n_results": 10,
            }
        }


class SemanticResult(BaseModel):
    """A single semantic search result."""
    record_id: str
    record_type: str
    document_text: str
    similarity_score: float
    risk_score: float
    metadata: dict


# ── Helper ─────────────────────────────────────────────────────

def _require_ready_case(case_id: str, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status != "ready":
        raise HTTPException(status_code=400,
                            detail=f"Case not ready. Status: {case.status}")
    return case


def _enrich_with_db_data(results: list[dict], db: Session) -> list[dict]:
    """
    ChromaDB returns document text + metadata.
    This function adds the full DB record details (full message text, etc.)
    so the frontend gets complete information.
    """
    enriched = []
    for result in results:
        record_type = result.get("record_type")
        record_id = result.get("record_id")
        full_record = {}

        if record_type == "chat":
            chat = db.query(ChatMessage).filter(ChatMessage.id == record_id).first()
            if chat:
                full_record = {
                    "id": chat.id,
                    "platform": chat.platform,
                    "sender": chat.sender,
                    "receiver": chat.receiver,
                    "message": chat.message_text,
                    "timestamp": chat.timestamp,
                    "direction": chat.direction,
                    "is_flagged": chat.is_flagged,
                    "entities": chat.entities_json,
                }

        elif record_type == "call":
            call = db.query(CallRecord).filter(CallRecord.id == record_id).first()
            if call:
                full_record = {
                    "id": call.id,
                    "caller": call.caller_number,
                    "receiver": call.receiver_number,
                    "duration_seconds": call.duration_seconds,
                    "call_type": call.call_type,
                    "platform": call.platform,
                    "timestamp": call.timestamp,
                    "is_foreign": call.is_foreign_number,
                }

        elif record_type == "contact":
            contact = db.query(Contact).filter(Contact.id == record_id).first()
            if contact:
                full_record = {
                    "id": contact.id,
                    "name": contact.name,
                    "phone_numbers": contact.phone_numbers,
                    "email_addresses": contact.email_addresses,
                    "organization": contact.organization,
                }

        enriched.append({
            "similarity_score": result["similarity_score"],
            "risk_score": result["risk_score"],
            "record_type": record_type,
            "record": full_record,
            "matched_text": result["document"],
        })

    return enriched


# ── Endpoints ──────────────────────────────────────────────────

@router.post("/{case_id}/semantic")
def semantic_search(
    case_id: str,
    request: SemanticSearchRequest,
    db: Session = Depends(get_db),
):
    """
    Semantic similarity search across forensic records.

    This finds records that are MEANINGFULLY SIMILAR to your query,
    not just exact keyword matches.

    Examples of what this can find:
    - Query: "crypto payment"
      Finds: "send BTC", "wallet transfer", "USDT bhej", "coin transaction"

    - Query: "meeting at night"
      Finds: "11 baje mil", "raat ko aao", "same place tonight"

    - Query: "foreign communication"
      Finds: calls/messages with UAE, UK, Pakistan numbers
    """
    _require_ready_case(case_id, db)
    vs = get_vector_store()

    results = vs.semantic_search(
        query=request.query,
        case_id=case_id,
        n_results=request.n_results,
        record_type=request.record_type if request.record_type else None,
        min_risk=request.min_risk if request.min_risk > 0 else None,
    )

    enriched = _enrich_with_db_data(results, db)

    return {
        "query": request.query,
        "search_type": "semantic",
        "total_found": len(enriched),
        "results": enriched,
    }


@router.get("/{case_id}/similar/{record_id}")
def find_similar_records(
    case_id: str,
    record_id: str,
    n_results: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    """
    Given a specific chat/call record ID, find other records similar to it.
    Useful for: "I found this suspicious message — show me more like it."
    """
    _require_ready_case(case_id, db)

    # Get the source record's text
    chat = db.query(ChatMessage).filter(
        ChatMessage.id == record_id,
        ChatMessage.case_id == case_id
    ).first()

    if not chat:
        raise HTTPException(status_code=404, detail="Record not found")

    vs = get_vector_store()

    # Search using this message as the query
    results = vs.semantic_search(
        query=chat.message_text,
        case_id=case_id,
        n_results=n_results + 1,  # +1 because the record itself will appear
    )

    # Remove the source record from results
    results = [r for r in results if r["record_id"] != record_id][:n_results]
    enriched = _enrich_with_db_data(results, db)

    return {
        "source_record": {
            "id": chat.id,
            "message": chat.message_text,
            "sender": chat.sender,
        },
        "similar_records": enriched,
        "total_found": len(enriched),
    }


@router.get("/{case_id}/index-status")
def get_index_status(case_id: str, db: Session = Depends(get_db)):
    """
    Check how many records from this case are indexed in ChromaDB.
    If count is 0, the case needs re-indexing.
    """
    _require_ready_case(case_id, db)

    # Count records in SQL
    total_chats = db.query(ChatMessage).filter(ChatMessage.case_id == case_id).count()
    total_calls = db.query(CallRecord).filter(CallRecord.case_id == case_id).count()
    total_contacts = db.query(Contact).filter(Contact.case_id == case_id).count()

    # Count in ChromaDB
    vs = get_vector_store()
    chroma_stats = vs.get_case_stats(case_id)

    return {
        "case_id": case_id,
        "sqlite_records": {
            "chats": total_chats,
            "calls": total_calls,
            "contacts": total_contacts,
            "total": total_chats + total_calls + total_contacts,
        },
        "chromadb_indexed": chroma_stats["total_indexed"],
        "is_fully_indexed": chroma_stats["total_indexed"] > 0,
    }


@router.post("/{case_id}/reindex")
def reindex_case(case_id: str, db: Session = Depends(get_db)):
    """
    Re-index all records for a case into ChromaDB.
    Use this if semantic search returns 0 results for an existing case.
    This is also called automatically during file upload (Phase 2 update).
    """
    case = _require_ready_case(case_id, db)
    vs = get_vector_store()

    # Delete existing vectors then re-index all at once
    vs.delete_case_documents(case_id)

    chats = db.query(ChatMessage).filter(ChatMessage.case_id == case_id).all()
    calls = db.query(CallRecord).filter(CallRecord.case_id == case_id).all()
    contacts = db.query(Contact).filter(Contact.case_id == case_id).all()

    counts = vs.index_all(case_id, chats, calls, contacts)
    total = counts["chats"] + counts["calls"] + counts["contacts"]

    return {
        "success": True,
        "case_id": case_id,
        "indexed": {**counts, "total": total},
        "message": f"Successfully indexed {total} records into ChromaDB.",
    }