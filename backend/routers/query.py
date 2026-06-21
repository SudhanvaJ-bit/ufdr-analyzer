"""
routers/query.py — FastAPI routes for searching and querying forensic data.

WHY THIS FILE EXISTS:
  Officers need to find specific data quickly. This router provides:
  1. Keyword search (fast, no AI needed, works without API key)
  2. Filtered queries (by date, risk score, platform, etc.)
  3. Pre-built forensic queries ("show all crypto chats", "foreign numbers")
  4. AI natural language query (Phase 3 — placeholder here)

IMPORTANT:
  All queries are scoped to a specific case_id.
  An officer can only query their own uploaded case.
  (Multi-user auth is Phase 7.)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from backend.database import get_db
from backend.models import Case, ChatMessage, CallRecord, Contact, MediaFile

router = APIRouter(prefix="/query", tags=["Query"])


def _case_exists(case_id: str, db: Session) -> Case:
    """Helper: raise 404 if case doesn't exist or isn't ready."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Case is not ready yet. Status: {case.status}"
        )
    return case


@router.get("/{case_id}/chats/search")
def search_chats(
    case_id: str,
    q: str = Query(..., description="Keyword to search in messages"),
    min_risk: float = Query(0.0, description="Minimum risk score (0-10)"),
    platform: str = Query("", description="Filter by platform (WhatsApp, Telegram, SMS)"),
    flagged_only: bool = Query(False, description="Show only auto-flagged messages"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """
    Search chat messages by keyword + optional filters.

    Examples:
    - GET /query/{case_id}/chats/search?q=bitcoin
    - GET /query/{case_id}/chats/search?q=delivery&min_risk=3
    - GET /query/{case_id}/chats/search?q=&flagged_only=true
    """
    _case_exists(case_id, db)

    query = db.query(ChatMessage).filter(ChatMessage.case_id == case_id)

    # Keyword search in message text (case-insensitive via LIKE)
    if q:
        query = query.filter(ChatMessage.message_text.ilike(f"%{q}%"))

    # Risk score filter
    if min_risk > 0:
        query = query.filter(ChatMessage.risk_score >= min_risk)

    # Platform filter
    if platform:
        query = query.filter(ChatMessage.platform.ilike(f"%{platform}%"))

    # Flagged only
    if flagged_only:
        query = query.filter(ChatMessage.is_flagged == True)

    # Order by risk score (highest first)
    chats = query.order_by(ChatMessage.risk_score.desc()).limit(limit).all()

    return {
        "query": q,
        "total_found": len(chats),
        "results": [
            {
                "id": c.id,
                "platform": c.platform,
                "sender": c.sender,
                "receiver": c.receiver,
                "message": c.message_text,
                "timestamp": c.timestamp,
                "risk_score": c.risk_score,
                "is_flagged": c.is_flagged,
                "entities": c.entities_json,
            }
            for c in chats
        ],
    }


@router.get("/{case_id}/chats/crypto")
def get_crypto_chats(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Pre-built query: Find all messages containing cryptocurrency addresses."""
    _case_exists(case_id, db)

    # We look for messages where entities_json has crypto_addresses
    # SQLite JSON querying is limited, so we use risk_score as proxy
    # (any message with crypto address gets risk >= 3.0)
    chats = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.case_id == case_id,
            ChatMessage.risk_score >= 3.0,
        )
        .order_by(ChatMessage.risk_score.desc())
        .all()
    )

    # Further filter: only those with actual crypto addresses
    crypto_chats = [
        c for c in chats
        if c.entities_json and c.entities_json.get("crypto_addresses")
    ]

    return {
        "query_type": "crypto_chats",
        "total_found": len(crypto_chats),
        "results": [
            {
                "id": c.id,
                "sender": c.sender,
                "receiver": c.receiver,
                "message": c.message_text,
                "timestamp": c.timestamp,
                "crypto_addresses": c.entities_json.get("crypto_addresses", []),
                "crypto_types": c.entities_json.get("crypto_types", []),
                "risk_score": c.risk_score,
            }
            for c in crypto_chats
        ],
    }


@router.get("/{case_id}/calls/foreign")
def get_foreign_calls(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Pre-built query: List all calls involving foreign phone numbers."""
    _case_exists(case_id, db)

    calls = (
        db.query(CallRecord)
        .filter(
            CallRecord.case_id == case_id,
            CallRecord.is_foreign_number == True,
        )
        .order_by(CallRecord.duration_seconds.desc())
        .all()
    )

    return {
        "query_type": "foreign_calls",
        "total_found": len(calls),
        "results": [
            {
                "id": c.id,
                "caller": c.caller_number,
                "receiver": c.receiver_number,
                "duration_minutes": round(c.duration_seconds / 60, 1),
                "call_type": c.call_type,
                "platform": c.platform,
                "timestamp": c.timestamp,
                "risk_score": c.risk_score,
            }
            for c in calls
        ],
    }


@router.get("/{case_id}/contacts/common")
def find_common_contacts(
    case_id: str,
    number_a: str = Query(..., description="First phone number"),
    number_b: str = Query(..., description="Second phone number"),
    db: Session = Depends(get_db),
):
    """
    Find contacts/numbers that communicated with BOTH suspect A and suspect B.
    This is 'link analysis' at its simplest form.

    Example: Who is a common contact between +919876543210 and +919988776655?
    """
    _case_exists(case_id, db)

    # Find all numbers that A communicated with
    chats_a = db.query(ChatMessage).filter(
        ChatMessage.case_id == case_id,
        or_(ChatMessage.sender == number_a, ChatMessage.receiver == number_a)
    ).all()

    contacts_of_a = set()
    for c in chats_a:
        if c.sender != number_a:
            contacts_of_a.add(c.sender)
        if c.receiver != number_a:
            contacts_of_a.add(c.receiver)

    # Find all numbers that B communicated with
    chats_b = db.query(ChatMessage).filter(
        ChatMessage.case_id == case_id,
        or_(ChatMessage.sender == number_b, ChatMessage.receiver == number_b)
    ).all()

    contacts_of_b = set()
    for c in chats_b:
        if c.sender != number_b:
            contacts_of_b.add(c.sender)
        if c.receiver != number_b:
            contacts_of_b.add(c.receiver)

    # Intersection = common contacts
    common = contacts_of_a.intersection(contacts_of_b)
    common.discard(number_a)
    common.discard(number_b)

    return {
        "query_type": "common_contacts",
        "suspect_a": number_a,
        "suspect_b": number_b,
        "contacts_of_a_count": len(contacts_of_a),
        "contacts_of_b_count": len(contacts_of_b),
        "common_contacts": list(common),
        "common_count": len(common),
    }


@router.get("/{case_id}/summary")
def get_case_summary(
    case_id: str,
    db: Session = Depends(get_db),
):
    """Get a statistical summary of a case — total records, risk breakdown, etc."""
    _case_exists(case_id, db)

    total_chats = db.query(ChatMessage).filter(ChatMessage.case_id == case_id).count()
    flagged_chats = db.query(ChatMessage).filter(
        ChatMessage.case_id == case_id, ChatMessage.is_flagged == True
    ).count()
    crypto_chats = db.query(ChatMessage).filter(
        ChatMessage.case_id == case_id, ChatMessage.risk_score >= 3.0
    ).count()

    total_calls = db.query(CallRecord).filter(CallRecord.case_id == case_id).count()
    foreign_calls = db.query(CallRecord).filter(
        CallRecord.case_id == case_id, CallRecord.is_foreign_number == True
    ).count()

    total_contacts = db.query(Contact).filter(Contact.case_id == case_id).count()
    total_media = db.query(MediaFile).filter(MediaFile.case_id == case_id).count()

    # Top 5 highest-risk messages
    top_risk = (
        db.query(ChatMessage)
        .filter(ChatMessage.case_id == case_id)
        .order_by(ChatMessage.risk_score.desc())
        .limit(5)
        .all()
    )

    return {
        "case_id": case_id,
        "summary": {
            "chats": {"total": total_chats, "flagged": flagged_chats, "high_risk": crypto_chats},
            "calls": {"total": total_calls, "foreign": foreign_calls},
            "contacts": {"total": total_contacts},
            "media": {"total": total_media},
        },
        "top_risk_messages": [
            {
                "sender": c.sender,
                "message_preview": c.message_text[:80] + "..." if len(c.message_text) > 80 else c.message_text,
                "risk_score": c.risk_score,
                "entities": c.entities_json,
            }
            for c in top_risk
        ],
    }
