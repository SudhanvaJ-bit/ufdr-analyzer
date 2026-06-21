# Project Tracker

> Update this file after every phase/step. If you start a new chat with a new
> AI session, paste the "How to explain current progress" section so it can
> pick up context instantly — or just re-upload the repo zip, which is even
> better since it can verify the actual code.

---

## Status: Phase 3 — RAG Q&A wired up (post-review fixes applied)

### What was completed
- Reviewed the full existing codebase (uploaded as a zip) against the
  README's claimed progress. Found the project was further along than its
  own README admitted — `backend/ai/llm_client.py` already had a complete
  three-tier LLM fallback (Gemini → OpenAI → offline summary), it just
  wasn't wired into an API endpoint yet.
- Fixed 5 real issues found during review:
  1. **Multi-case vectorizer collision** (critical): `chroma_store.py` used
     one shared TF-IDF vectorizer for the whole vector store, refit on
     every upload. This meant indexing a second case silently corrupted
     search for the first case (different vocabulary → different vector
     meaning). Fixed by giving each `case_id` its own persisted vectorizer
     file (`vectorizers/tfidf_vectorizer_{case_id}.pkl`), loaded/cached per
     case. `delete_case_documents` now also cleans up that case's
     vectorizer file.
  2. **`get_case_stats` bug**: was returning the *entire* collection's
     document count instead of the count for the specific `case_id`
     requested — misleading once more than one case exists. Fixed to
     filter by `case_id`.
  3. **AI router never wired in**: `llm_client.py` existed but nothing
     called it. Created `backend/ai/query_engine.py` (the RAG glue: retrieve
     evidence via ChromaDB → build context → ask LLM → return answer +
     cited sources) and `backend/routers/ai.py` (exposes `POST
     /ai/{case_id}/ask` and `GET /ai/mode`). Registered the router in
     `main.py`.
  4. **Gemini system-prompt bug**: `LLMClient.ask()` defaulted
     `system_prompt=""`, and the Gemini path (unlike the OpenAI path) had
     no fallback to `FORENSIC_SYSTEM_PROMPT` — meaning Gemini answers were
     never actually grounded by the "answer ONLY from this evidence"
     instruction unless the caller passed it explicitly. Fixed by defaulting
     to `FORENSIC_SYSTEM_PROMPT` inside `ask()` itself, so every call path
     gets it automatically.
  5. **Missing dependency**: `chroma_store.py` imports `scikit-learn`
     directly, but it wasn't in `requirements.txt` — would have caused a
     hard crash on first case upload on a fresh install. Added.
- Cleaned up mangled emoji/encoding artifacts in startup print statements
  (`main.py`, `database.py`) — cosmetic but would look broken in logs/demo.
- Noted but did NOT fix (deliberately deferred, not urgent):
  - `timestamp` columns are `String` not `DateTime` across all models —
    works fine as long as the parser's ISO normalization succeeds, but
    sorting/timeline queries are technically fragile if a malformed
    timestamp slips through. Revisit before building Phase 7 (timeline
    reconstruction), since that phase will lean on timestamp ordering.
  - `INDIAN_PHONE_PATTERN` in `entity_extractor.py` is defined but unused —
    dead code, not a bug, low priority.

### Files created/updated
- **Created:** `backend/ai/query_engine.py`, `backend/routers/ai.py`
- **Updated:** `backend/vector_store/chroma_store.py` (per-case vectorizer
  fix + stats fix), `backend/ai/llm_client.py` (system prompt default fix),
  `backend/main.py` (router registration + encoding fix), `backend/database.py`
  (encoding fix), `requirements.txt` (added scikit-learn)
- **Unchanged, reviewed and confirmed solid:** `backend/parsers/ufdr_parser.py`,
  `backend/extractors/entity_extractor.py`, `backend/models.py`,
  `backend/config.py`, `backend/routers/upload.py`, `backend/routers/query.py`,
  `backend/routers/search.py`

### Current architecture status
Real, working pipeline end-to-end:
```
Upload (JSON/ZIP/CSV) → Parser → Entity Extractor → SQLite (SQLAlchemy)
                                        │
                                        ▼
                              ChromaDB (per-case TF-IDF vectors)
                                        │
                    ┌───────────────────┼────────────────────┐
                    ▼                   ▼                    ▼
            SQL keyword search   Semantic search      RAG Q&A (NEW)
              (query.py)           (search.py)         (ai.py + query_engine.py)
                                                          → LLMClient
                                                          (Gemini/OpenAI/offline)
```
Not yet built: link analysis graph (NetworkX), risk scoring beyond the
per-record extractor score, PDF report generation, frontend, Docker.

### Pending tasks
- Get a Gemini API key (free tier) and test `/ai/{case_id}/ask` in "gemini"
  mode, not just offline mode — currently only syntax-checked and manually
  traced, not actually run, since this review environment has no network
  access and not all dependencies installed.
- Phase 5 (already partially done via TF-IDF semantic search — could
  optionally revisit upgrading to sentence-transformers later, documented
  as a deliberate tradeoff, not urgent).
- Phase 6: entity extraction is largely done (regex-based); spaCy NER for
  names/locations specifically is not yet integrated despite being imported
  in `requirements.txt` — confirm whether this is planned next.
- Phase 7: Timeline reconstruction endpoint — revisit the timestamp-as-String
  fragility noted above before building this.
- Phase 8: Link analysis / relationship graph (NetworkX) — `find_common_contacts`
  in `query.py` is a basic version of this already; full graph view is still
  pending.
- Phase 9: Suspicious pattern detection + aggregate risk scoring (currently
  risk score is per-record only, not per-contact/case-level pattern detection).
- Phase 10: PDF report generation.
- Phase 11: Frontend (Streamlit, per original plan).
- Phase 12: Docker + deployment.
- Phase 13: GitHub polish, screenshots, demo video.

### Known issues
- `timestamp` stored as `String`, not `DateTime` — flagged above, revisit
  before Phase 7.
- No Gemini API key configured yet — `/ai/{case_id}/ask` currently runs in
  "offline" mode (still functional, just returns a structured evidence list
  instead of an AI-written answer).
- Project has not been run/tested in an environment with all dependencies
  installed since these fixes were applied — recommend running locally and
  re-testing the upload → index → ask flow before continuing to Phase 8.

### Next step
Get a Gemini API key, add it to `.env`, run the backend locally, upload
`sample_ufdr/sample_case_001.json`, and test:
1. `GET /search/{case_id}/index-status` — confirm indexing worked
2. `POST /ai/{case_id}/ask` with a real question — confirm Gemini mode
   activates and returns a grounded, cited answer
3. Then move to Phase 8 (link analysis graph) or Phase 9 (risk scoring),
   per your preference.

### How to explain current progress to a new AI chat
> "I'm building an AI-Based UFDR Forensic Intelligence platform (SIH
> problem ID 25198) — FastAPI backend, SQLite + SQLAlchemy, ChromaDB with
> per-case TF-IDF vectors for semantic search, and a RAG Q&A endpoint
> (`POST /ai/{case_id}/ask`) with a Gemini → OpenAI → offline fallback
> chain. Entity extraction (regex for phones/crypto/emails/keywords) and
> risk scoring are done per-record. Just had a code review that fixed a
> multi-case vectorizer bug and wired up the previously-unused AI router.
> Next: get a Gemini key tested, then move to link analysis (NetworkX) and
> aggregate risk scoring. Full code is in the attached repo zip — please
> read it directly rather than relying on this summary."

---

## Phase Log Template (copy this block for each new phase)

```
## Status: Phase N — <name>

### What was completed
-

### Files created/updated
-

### Current architecture status
-

### Pending tasks
-

### Known issues
-

### Next step
-

### How to explain current progress to a new AI chat
>
```
