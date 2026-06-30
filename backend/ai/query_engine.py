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

KNOWN LIMITATION FOUND AND FIXED: MULTI-PART QUESTIONS.
  A single embedding vector represents one "topic." Asking one combined
  question covering two unrelated topics (e.g. "Are there foreign
  communications AND is there evidence of crypto transactions?") produces
  one blended query vector that may not represent either topic well. If
  one topic has far more matching records in the case than the other
  (e.g. many foreign-call records vs. very few crypto-chat records), the
  more numerous topic can dominate ALL top-K retrieval slots, silently
  crowding out the other topic's evidence entirely — even though asking
  about that topic ALONE retrieves it correctly. This was observed live:
  asking about crypto alone correctly surfaced the BTC/USDT messages;
  asking "foreign communications AND crypto" in one question retrieved
  only foreign-call evidence and the model (correctly, given what it was
  shown) reported no crypto evidence existed.

  FIX: split the question into sub-questions on common conjunctions
  ("and", "also", "as well as", semicolons, question marks), retrieve
  top-K independently for EACH sub-question, then merge and de-duplicate
  before building the context. This guarantees every distinct topic in a
  multi-part question gets its own fair share of retrieval slots instead
  of competing in one shared pool. This is a known, real limitation of
  single-vector retrieval — not specific to this LLM or this case data —
  and worth being able to explain directly in an interview.

INTERVIEW EXPLANATION:
  "My RAG pipeline retrieves the top-K most relevant records for a case
  from ChromaDB, builds a context block from them, and asks the LLM to
  answer using ONLY that context. I found during testing that asking a
  combined, multi-topic question could let one topic's evidence
  statistically crowd out another's during retrieval, even though each
  topic retrieved correctly on its own. I fixed it by splitting multi-part
  questions and retrieving independently per sub-question before merging
  — a single embedding can't represent two unrelated topics well, so
  giving each its own retrieval pass avoids one dominating the other."
"""

import re
from backend.vector_store.chroma_store import get_vector_store
from backend.ai.llm_client import LLMClient, FORENSIC_SYSTEM_PROMPT

# Module-level singleton so we don't reconstruct the LLM client (which
# detects the active mode: gemini/openai/offline) on every request.
_llm_client: LLMClient | None = None

# Patterns used to split a multi-part question into independent
# sub-questions. Deliberately simple and rule-based rather than another
# LLM call — keeps latency/cost low and is easy to reason about and
# explain. Order matters: try more specific separators before falling
# back to a bare " and ".
#
# Beyond explicit conjunctions/punctuation, this also catches a second
# imperative verb phrase starting mid-sentence with NO connecting word
# at all (e.g. "Are there foreign communications look for crypto
# evidence") — found necessary after a real query with exactly this
# phrasing (no "and", no comma, no question mark between the two topics)
# failed to split with conjunction-only patterns and silently dropped
# the second topic's evidence. This is a heuristic, not a parser: it
# only catches phrasings that start with one of these specific verbs,
# and will NOT catch a compound question with no lexical signal at all
# (e.g. "Foreign numbers crypto transactions" has no split point this
# regex can find). Documented as a known limitation, not a guarantee.
_SPLIT_PATTERN = re.compile(
    r"\s*(?:,?\s+and also\s+|,?\s+as well as\s+|;\s*|\?\s+|,?\s+and\s+|"
    r"(?<=\w)\s+(?=look for\s)|(?<=\w)\s+(?=find\s)|"
    r"(?<=\w)\s+(?=check\s)|(?<=\w)\s+(?=search for\s))",
    re.IGNORECASE,
)

MIN_SUBQUESTION_WORDS = 3  # ignore fragments too short to be a real sub-question


def _split_into_subquestions(question: str) -> list[str]:
    """
    Split a question into independent sub-questions on common
    conjunctions/punctuation. Returns [question] unchanged if no split
    points are found or every split-off fragment is too short to be
    meaningful on its own (e.g. "salt and pepper" shouldn't split).
    """
    question = question.strip()
    if not question:
        return []

    parts = [p.strip() for p in _SPLIT_PATTERN.split(question) if p.strip()]
    parts = [p for p in parts if len(p.split()) >= MIN_SUBQUESTION_WORDS]

    if len(parts) <= 1:
        return [question]
    return parts


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


def _retrieve_for_question(
    case_id: str,
    question: str,
    record_type: str | None,
    min_risk: float | None,
    top_k: int,
) -> list[dict]:
    vs = get_vector_store()
    return vs.semantic_search(
        query=question,
        case_id=case_id,
        n_results=top_k,
        record_type=record_type,
        min_risk=min_risk,
    )


def ask_question(
    case_id: str,
    question: str,
    record_type: str | None = None,
    min_risk: float | None = None,
    top_k: int = 15,
) -> dict:
    """
    Main RAG entry point.

    1. Split the question into independent sub-questions if it contains
       multiple distinct topics (see module docstring for why).
    2. Retrieve top_k evidence records PER sub-question, scoped to
       case_id, then merge and de-duplicate by record_id — this is what
       prevents one topic's evidence from crowding out another's.
    3. Build a numbered context block from the merged evidence.
    4. Ask the LLM to answer the FULL original question using ONLY that
       context.
    5. Return the answer plus the exact source records used, so every
       claim in the answer can be traced back to real evidence.

    Returns:
        {
            "answer": str,
            "mode": "gemini" | "openai" | "offline",
            "sources": [ {record_id, record_type, risk_score, text}, ... ],
            "evidence_count": int,
            "subquestions": list[str],  # what the question was split into
        }
    """
    subquestions = _split_into_subquestions(question)

    seen_record_ids = set()
    evidence: list[dict] = []
    for subq in subquestions:
        results = _retrieve_for_question(case_id, subq, record_type, min_risk, top_k)
        for item in results:
            rid = item.get("record_id", "")
            if rid and rid in seen_record_ids:
                continue
            seen_record_ids.add(rid)
            evidence.append(item)

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
            "subquestions": subquestions,
        }

    context = _build_context(evidence)

    client = _get_llm_client()
    result = client.ask(
        question=question,  # the FULL original question, not a sub-question
        context=context,
        system_prompt=FORENSIC_SYSTEM_PROMPT,
        topic_count=len(subquestions),
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
        "subquestions": subquestions,
    }