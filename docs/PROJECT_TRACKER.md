# Project Tracker

> Update this file after every phase/step. If you start a new chat with a new
> AI session, paste the "How to explain current progress" section so it can
> pick up context instantly — or just re-upload the repo zip, which is even
> better since it can verify the actual code.

---

## Status: Phase 9 — Risk scoring built on top of the link analysis graph

### What was completed
- Built `backend/analysis/risk_scorer.py`: combines per-contact message
  content risk (avg + peak, from existing entity extraction) with their
  Phase 8 graph position (betweenness centrality, normalized weighted
  degree) into one transparent, explainable combined score (0-10).
- Deliberate weighting: 60% content risk (40% avg + 20% peak), 40%
  network risk (25% betweenness + 15% normalized weighted degree) — a
  documented design stance that direct evidence (message content) should
  outweigh circumstantial inference (network position), not an arbitrary
  tuning choice.
- Added 4 explicit, named pattern flags (bridges_clusters, foreign_contact,
  high_risk_content, high_network_volume), each worth +1 bonus point,
  capped at 10 total.
- Every score returns its full breakdown — no black-box numbers.
- New endpoint: `GET /analysis/{case_id}/risk-ranking`.
- **Validated against real sample data**: the #1 ranked contact was a
  lower-message-volume foreign number that hit all 4 pattern flags at
  once, NOT the highest-volume talker or the Phase-8 "biggest hub" (which
  dropped to 5th place specifically for having zero betweenness despite
  the most raw connections). This confirms the formula does what it was
  designed to do — convergence of multiple independent signals beats raw
  popularity.

### Files created/updated
- **Created:** `backend/analysis/risk_scorer.py`
- **Updated:** `backend/routers/analysis.py` (new `/risk-ranking` endpoint)

### Current architecture status
```
Upload → Parser → Entity Extractor → SQLite
                        │
        ┌───────────────┼───────────────────┬─────────────────┐
        ▼               ▼                    ▼                 ▼
  ChromaDB (RAG)   SQL/Semantic     Link Analysis Graph   Risk Scoring (NEW)
                    search          (Phase 8)              (Phase 9)
                                    → centrality            → combines content
                                                               risk + graph
                                                               position
                                                            → /risk-ranking
```
All originally planned core analysis phases (3, 8, 9) are now complete
and validated on real data. Remaining: PDF reports (10), frontend (11),
Docker (12), GitHub polish (13).

### Pending tasks
- Phase 10: PDF report generation — could now pull directly from
  risk-ranking + key-players + RAG summaries as report content.
- Phase 11: Streamlit dashboard — biggest visual payoff remaining, since
  the graph and risk ranking currently only return JSON.
- Phase 12: Docker + deployment.
- Phase 13: GitHub polish, screenshots, demo video.
- Known limitation, not yet addressed: `score_contacts` treats being a
  sender OR receiver of a risky message equally — a more refined version
  might weight the sender's own risk more heavily than a receiver's,
  since receiving one risky message doesn't necessarily implicate the
  receiver the way sending one does. Documented here as a known
  simplification rather than fixed now, since the current behavior is
  still defensible (both participants are part of the conversation).

### Known issues
- None found during this phase's testing (verified via isolated test
  harness due to a sandboxed environment lacking `pydantic-settings`;
  logic confirmed correct against real sample data).

### Next step
Phase 10 (PDF reports), Phase 11 (Streamlit dashboard), or Phase 12/13 —
your call. Dashboard is probably highest-leverage next since none of the
graph/risk output has been visualized yet, only returned as JSON.

### How to explain current progress to a new AI chat
> "I'm building an AI-Based UFDR Forensic Intelligence platform (SIH
> problem ID 25198). Backend: FastAPI, SQLite+SQLAlchemy, ChromaDB with
> per-case TF-IDF for semantic search, Gemini-powered RAG Q&A with
> citations and a tested fallback chain, a NetworkX link analysis graph
> with degree/betweenness centrality, and now a case-level risk scoring
> system that combines message content risk with graph position into one
> transparent, explainable score — validated on real data, where the
> top-ranked contact wasn't the busiest talker but the one where multiple
> independent risk signals converged. Next: PDF reports, frontend
> dashboard, or deployment. Full code is in the attached repo — please
> read it directly rather than relying on this summary."

---

## Status: Phase 8 — Link analysis graph (NetworkX) complete

### What was completed
- Built `backend/analysis/graph_analyzer.py`: constructs an undirected,
  weighted communication graph from a case's chats AND calls combined
  (one graph, not two separate ones) — nodes are phone numbers, edges
  accumulate chat_count/call_count/total_risk/max_risk per pair, and edge
  weight combines communication frequency with cumulative risk (risk
  weighted 2x relative to raw count, so a pair with 2 high-risk crypto
  messages outranks a pair with 20 mundane ones).
- Computed two centrality metrics per node:
  - **Degree centrality** — how widely connected a number is (a "hub").
  - **Betweenness centrality** — how often a number bridges two
    otherwise-disconnected people (a "broker"); validated on real sample
    data that this surfaces different, non-obvious people than degree
    centrality alone would (see test results below).
- Built `backend/routers/analysis.py` with two endpoints:
  - `GET /analysis/{case_id}/graph` — full graph as nodes+edges JSON,
    frontend-visualization-ready.
  - `GET /analysis/{case_id}/key-players` — top hubs + top bridges in one
    call, the quick "who matters here" answer.
- Registered the router in `main.py`.
- **Validated against real sample data**, not just synthetic toy input:
  ran the actual 100-chat/50-call sample case through the pipeline (with
  a crude crypto-keyword risk proxy standing in for the real extractor
  scores during this standalone test). Result: 7 nodes, 18 edges. The top
  hub by degree centrality (most widely connected) had ZERO betweenness
  centrality, while two other numbers — including the UK foreign number
  — emerged as the actual structural bridges. This is exactly the kind
  of non-obvious signal the betweenness metric exists to surface, and
  it showed up on the first real test, not just the synthetic example.

### Files created/updated
- **Created:** `backend/analysis/graph_analyzer.py`, `backend/routers/analysis.py`
- **Updated:** `backend/main.py` (router registration)

### Current architecture status
```
Upload → Parser → Entity Extractor → SQLite
                        │
        ┌───────────────┼───────────────────┐
        ▼               ▼                    ▼
  ChromaDB (RAG)   SQL/Semantic search   Link Analysis Graph (NEW)
                                          (analysis.py + graph_analyzer.py)
                                          → degree + betweenness centrality
                                          → /analysis/{id}/graph
                                          → /analysis/{id}/key-players
```
Not yet built: case-level suspicious pattern detection / aggregate risk
scoring (Phase 9 — can now build on top of this graph, e.g. flag high-
betweenness nodes as a risk signal), PDF reports, frontend, Docker.

### Pending tasks
- Phase 9: Suspicious pattern detection + aggregate/case-level risk
  scoring — now sequenced to build ON TOP of this graph (e.g. "flag
  numbers with high betweenness centrality + high weighted_degree as
  priority leads") rather than as an unrelated feature.
- Consider exposing edge breakdown (chat_count vs call_count) more
  prominently in a future frontend — currently in the API response but
  not surfaced anywhere visual yet.
- `betweenness_centrality` is O(V*E) — fine for single-case graphs of the
  current scale (tested at 7 nodes/18 edges), but would need the `k`
  sampling parameter in `nx.betweenness_centrality` if a future case has
  hundreds+ of distinct contacts.

### Known issues
- None found during this phase's testing. The zero-betweenness filter fix
  was verified live: `bridges` now correctly returns 4 entries (not
  padded to 5), with the top hub (`+919090909090`, betweenness=0)
  correctly excluded despite leading the `hubs` list.

### Next step
Build Phase 9 (risk scoring / suspicious pattern detection) using the
graph's centrality output as one of its inputs, OR move to Phase 4
(Streamlit dashboard) if a visual payoff is wanted before going deeper
analytically — your call.

### How to explain current progress to a new AI chat
> "I'm building an AI-Based UFDR Forensic Intelligence platform (SIH
> problem ID 25198). Backend: FastAPI, SQLite+SQLAlchemy, ChromaDB with
> per-case TF-IDF for semantic search, a RAG Q&A endpoint with a Gemini →
> OpenAI → offline fallback chain (tested live, including surviving a
> real Gemini model deprecation mid-project), and now a NetworkX-based
> link analysis graph computing degree and betweenness centrality across
> combined chat+call data, exposed via `/analysis/{case_id}/graph` and
> `/analysis/{case_id}/key-players`. Validated on real sample data, not
> just synthetic tests. Next: case-level risk scoring built on top of the
> graph, or the frontend dashboard. Full code is in the attached repo —
> please read it directly rather than relying on this summary."

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