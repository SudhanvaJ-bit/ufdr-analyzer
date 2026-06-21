"""
query_engine.py — RAG (Retrieve-Augment-Generate) pipeline for natural
language Q&A over a case's forensic evidence.

WHY THIS FILE EXISTS:
  chroma_store.py knows how to retrieve relevant evidence.
  llm_client.py knows how to call an LLM (or fall back offline).
  Neither of them should know about the other — this file is the glue
  that combines "retrieve relevant evidence" with "ask the LLM to answer
  using only that evidence", and is also where evidence-citation metadata
  gets attached to the final answer.

WHY THIS MATTERS (GROUNDING):
  The single most important design decision in this whole RAG pipeline is
  that the LLM is never given free rein — it only ever sees the evidence
  this engine retrieved, and the system prompt instructs it to answer
  ONLY from that evidence. The API response also returns the literal
  source records used, so an investigating officer (or a court) can
  verify every claim against an actual evidence row instead of trusting
  the AI's word for it.

INTERVIEW EXPLANATION:
  "My RAG pipeline retrieves the top-K most relevant records for a case
  from ChromaDB, builds a context block from them, and asks the LLM to
  answer using ONLY that context. I return both the generated answer and
  the exact source records it was based on, so every claim is traceable
  back to real evidence — that's the core requirement for a forensic
  tool, where 'the AI said so' can never be the final word."
"""

from backend.vector_store.chroma_store import get_vector_store
from backend.ai.llm_client import LLMClient, FORENSIC_SYSTEM_PROMPT

# Module-level singleton so we don't reconstruct the LLM client (which
# detects the active mode: gemini/openai/offline) on every request.
_llm_client: LLMClient | None = None


def _get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def _build_context(evidence: list[dict]) -> str:
    """
    Turn retrieved evidence records into a numbered text block the LLM
    can read, and that a human can cross-reference against the
    "sources" list returned alongside the answer.
    """
    lines = []
    for i, item in enumerate(evidence, 1):
        record_type = item.get("record_type", "record")
        text = item.get("document", "")
        risk = item.get("risk_score", 0)
        lines.append(f"[{i}] ({record_type}, risk={risk}) {text}")
    return "\n".join(lines)


def ask_question(
    case_id: str,
    question: str,
    record_type: str | None = None,
    min_risk: float | None = None,
    top_k: int = 15,
) -> dict:
    """
    Main RAG entry point.

    1. Retrieve the top_k most relevant evidence records for this case
       (scoped to case_id so cases never leak into each other).
    2. Build a numbered context block from those records.
    3. Ask the LLM to answer the question using ONLY that context.
    4. Return the answer plus the exact source records used, so every
       claim in the answer can be traced back to real evidence.

    Returns:
        {
            "answer": str,
            "mode": "gemini" | "openai" | "offline",
            "sources": [ {record_id, record_type, risk_score, text}, ... ],
            "evidence_count": int,
        }
    """
    vs = get_vector_store()
    evidence = vs.semantic_search(
        query=question,
        case_id=case_id,
        n_results=top_k,
        record_type=record_type,
        min_risk=min_risk,
    )

    if not evidence:
        return {
            "answer": (
                "No relevant evidence was found in this case for that "
                "question. Try rephrasing, or check that the case has "
                "been indexed (see /search/{case_id}/index-status)."
            ),
            "mode": "offline",
            "sources": [],
            "evidence_count": 0,
        }

    context = _build_context(evidence)

    client = _get_llm_client()
    result = client.ask(
        question=question,
        context=context,
        system_prompt=FORENSIC_SYSTEM_PROMPT,
    )

    sources = [
        {
            "record_id": item.get("record_id", ""),
            "record_type": item.get("record_type", ""),
            "risk_score": item.get("risk_score", 0),
            "text": item.get("document", ""),
        }
        for item in evidence
    ]

    return {
        "answer": result["answer"],
        "mode": result["mode"],
        "sources": sources,
        "evidence_count": len(sources),
    }