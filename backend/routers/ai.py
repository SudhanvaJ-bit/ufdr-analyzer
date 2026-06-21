"""
routers/ai.py — Natural language Q&A endpoint (Phase 3: RAG).

WHY A SEPARATE ROUTER?
  search.py does retrieval only (semantic search, no generation).
  query.py does SQL keyword search.
  This router is where retrieval + generation come together: it calls
  query_engine.ask_question(), which retrieves evidence via ChromaDB and
  asks the LLM to answer using only that evidence.

ENDPOINTS IN THIS FILE:
  POST /ai/{case_id}/ask        — Ask a natural language question, get a
                                   grounded answer + cited source records.
  GET  /ai/{case_id}/mode       — Check whether Gemini/OpenAI/offline mode
                                   is currently active (useful for the
                                   frontend to show "AI: online/offline").
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db
from backend.models import Case
from backend.ai.query_engine import ask_question, _get_llm_client

router = APIRouter(prefix="/ai", tags=["AI Q&A (RAG)"])


class AskRequest(BaseModel):
    """Body for the natural language question endpoint."""
    question: str
    record_type: str = ""        # "chat", "call", "contact", or "" for all
    min_risk: float = 0.0
    top_k: int = 15

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Is there any evidence of cryptocurrency transactions?",
                "record_type": "",
                "min_risk": 0.0,
                "top_k": 15,
            }
        }


def _require_ready_case(case_id: str, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status != "ready":
        raise HTTPException(
            status_code=400, detail=f"Case not ready. Status: {case.status}"
        )
    return case


@router.post("/{case_id}/ask")
def ask(case_id: str, request: AskRequest, db: Session = Depends(get_db)):
    """
    Ask a natural language question about this case's evidence.

    The answer is grounded in retrieved evidence only — every claim the
    AI makes is backed by the "sources" list returned alongside it, so
    an officer can verify any statement against the actual record.

    Falls back automatically: Gemini -> OpenAI -> offline evidence
    summary, depending on which API keys are configured in .env.
    """
    _require_ready_case(case_id, db)

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    result = ask_question(
        case_id=case_id,
        question=request.question,
        record_type=request.record_type or None,
        min_risk=request.min_risk if request.min_risk > 0 else None,
        top_k=request.top_k,
    )

    return {
        "case_id": case_id,
        "question": request.question,
        **result,
    }


@router.get("/mode")
def get_ai_mode():
    """
    Report which LLM mode is currently active.
    Lets the frontend show e.g. "AI: Gemini" vs "AI: Offline mode —
    add GEMINI_API_KEY to .env for AI-generated answers."
    """
    client = _get_llm_client()
    return {
        "mode": client.mode,
        "ai_available": client.is_ai_available(),
    }