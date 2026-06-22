# Learning Notes

> One entry per file, added/updated whenever that file is created or
> meaningfully changed. This is your personal "why does this code exist and
> what would I say about it in an interview" reference.

---

## docs/ARCHITECTURE.md

**Purpose:** Single source of truth for system design — data flow, schema,
RAG/graph flows, deployment topology, scalability and security plans.

**Why this approach:** Writing architecture down *before* code forces
decisions (e.g., "what exactly is in the database vs. the vector store?")
that are much more expensive to fix after code exists. It's also the
document you'd hand an interviewer or a teammate first.

**Common pitfall:** Architecture docs that describe an idealized system you
never actually build. This one is written to match the phased roadmap
exactly — if a phase isn't built yet, the doc should say so honestly rather
than describing aspirational features as if they exist.

**Interview angle:** "Can you explain your architecture?" → walk the data
flow diagram left to right: ingestion → structured storage → parallel
embedding + entity extraction → vector search / graph analysis → RAG/risk
scoring → API → frontend.

---

## docs/PROJECT_TRACKER.md

**Purpose:** Running log of what's done, what's pending, and — critically —
a copy-pasteable summary so a new AI chat session (or a new teammate) can
get full context in one paragraph instead of re-reading everything.

**Why this approach:** Long multi-week projects built incrementally (often
across many separate AI chat sessions) lose context easily. This file is
the fix: it's the single thing you paste at the start of any new session.

**Interview angle:** Less about code, more about process — shows you can
manage a multi-week project with clear checkpoints rather than just
"vibe-coding" until something works.

---

(Further entries added starting Phase 1, once actual code files exist.)

---

## backend/analysis/risk_scorer.py (new — Phase 9)

**Purpose:** Combines per-message content risk (already computed by
`entity_extractor.py`) with each contact's position in the Phase 8
communication graph into one transparent, case-level risk score per
contact.

**Important functions/classes:**
- `score_contacts(chats, centrality)` — the main entry point; returns a
  `ContactRiskProfile` per number, covering everyone who appears in
  either the chat data or the graph (so calls-only contacts with no chat
  history still get scored on network risk alone).
- `ContactRiskProfile.to_dict()` — always returns the full breakdown
  (avg/max content risk, betweenness, weighted degree, flags) alongside
  the final number, never just the score by itself.
- `get_top_risk_contacts(profiles, top_n)` — ranks and serializes the
  top N.

**The formula, and why it's weighted this way:**
`combined = avg_content_risk*0.4 + max_content_risk*0.2 + (betweenness*10)*0.25
          + (normalized_weighted_degree*10)*0.15`, then +1 per triggered
pattern flag (foreign_contact, bridges_clusters, high_risk_content,
high_network_volume), capped at 10.

Content risk gets 60% combined weight, network risk 40%, because content
risk is direct evidence (a message literally contains a crypto address)
while network position is circumstantial inference (being well-connected
isn't proof of anything by itself — a family group admin is well-connected
too). A forensic tool should weight direct evidence over structural
inference; that's a deliberate stance, not an arbitrary tuning choice.

**Why a transparent rule-based formula instead of an ML model:** An
investigator needs to be able to ask "why was this person flagged?" and
get a real, inspectable answer — not "the model said so." Every score
returned by this module comes with its full breakdown.

**Validated on real sample data:** The #1 ranked contact wasn't the
highest-volume talker (51 messages) or the Phase-8 "biggest hub" by raw
connections — it was a lower-volume foreign number that triggered ALL
FOUR pattern flags simultaneously. The Phase-8 top hub actually fell to
5th place here, specifically because it has zero betweenness (doesn't
bridge any clusters) despite having the most connections. This is the
formula working as designed: convergence of independent signals beats
raw popularity.

**Common errors and how to debug:**
- *A contact appears with all-zero content risk but a nonzero score* →
  expected if they have no chat history but DO appear in the
  communication graph (e.g. calls-only) — their score comes entirely
  from network risk in that case, which is intentional, not a bug.
- *`normalized_weighted_degree` is always 0* → means `centrality` was
  empty or every weighted_degree was 0 (e.g. an empty case); check that
  the graph was actually built before scoring.

**Interview questions:**
- "Why 60/40 instead of, say, 50/50?" → direct evidence vs. circumstantial
  inference — be ready to say this explicitly, it's a designed stance.
- "How do you avoid this being a black box?" → every result includes its
  full numeric breakdown and which pattern flags fired, not just a score.
- "Walk me through a real result." → use the validated example above:
  busiest talker ≠ top risk score, because it didn't bridge any clusters.
- "What's a known limitation?" → currently treats sender and receiver of
  a risky message equally; a more refined version might weight the
  sender's own risk more heavily, since sending implicates more directly
  than receiving.

**Simple interview explanation:** "I combine each person's message
content risk with their position in the communication graph from Phase
8, weighted 60/40 toward content since that's direct evidence. I tested
it on real data and the top-ranked person wasn't the one with the most
messages — it was someone where several independent risk signals lined
up at once, which is exactly the kind of non-obvious lead this is meant
to surface."

---

## backend/analysis/graph_analyzer.py (new — Phase 8)

**Purpose:** Builds an undirected, weighted communication graph from a
case's chats and calls combined, and computes centrality metrics to
identify key people in the network.

**Important functions/classes:**
- `build_communication_graph(chats, calls)` — accumulates per-pair stats
  (chat_count, call_count, total_risk, max_risk) across both record types
  into ONE edge per pair, then builds the NetworkX graph.
- `_edge_weight(count, total_risk)` — combines frequency and risk into a
  single weight, with risk weighted 2x relative to raw count, so a pair
  with a couple of high-risk crypto messages outranks a pair with many
  mundane ones.
- `compute_centrality(graph)` — returns degree centrality, betweenness
  centrality, weighted degree, and connection count per node.
- `get_top_hubs(centrality, top_n)` / `get_top_connectors(centrality, top_n)`
  — convenience rankings by degree vs. betweenness respectively.

**Why combine chats AND calls into ONE graph instead of two:** A suspect
who mostly calls one contact and mostly texts another would be split
across two incomplete pictures with separate graphs. One combined graph
better reflects real relationship strength, and the edge data still
records the chat/call breakdown separately so nothing is lost.

**Why two centrality metrics, not just one:** Degree centrality answers
"who talks to the most people" (a hub/organizer). Betweenness centrality
answers "who sits on the path between two people who don't talk
directly" (a bridge/broker). These can surface completely different
people — validated on real sample data where the top hub by degree had
ZERO betweenness, while two other, less-connected-looking numbers turned
out to be the actual structural bridges. A bridge can be a low-volume
coordinator who'd never show up if you only ranked by message count.

**Common errors and how to debug:**
- *Graph is empty / `compute_centrality` returns `{}`* → check that
  chats/calls actually have non-empty `sender`/`receiver` or
  `caller_number`/`receiver_number` fields; malformed records with a
  missing number or a self-loop (sender == receiver) are silently
  skipped rather than crashing.
- *Betweenness centrality is slow on a very large case* → NetworkX's
  betweenness algorithm is O(V×E); for hundreds+ of distinct contacts,
  pass the `k` parameter to `nx.betweenness_centrality` to sample instead
  of computing exactly.

**Interview questions:**
- "Why betweenness centrality and not just counting messages?" → exactly
  the hub-vs-bridge distinction above; a great concrete example to walk
  through if asked.
- "How do you weight edges, and why?" → frequency + 2x risk multiplier;
  explain the reasoning (a couple of high-risk messages should matter
  more than a lot of bland ones).
- "How would this scale to a case with thousands of contacts?" → mention
  the betweenness sampling parameter, and that in production you might
  also restrict the graph to flagged/high-risk records only rather than
  every single message.

**Simple interview explanation:** "I build one graph combining both
chats and calls, with edges weighted by how often two people communicated
and how risky those communications were. Then I compute two different
centrality scores — one finds the most talkative hubs, the other finds
the people who bridge separate groups, which is often the more
interesting lead even when they're not the most active person in the
data."

**Follow-up fix found during live testing:** The first version of
`get_top_connectors` returned the top-N nodes by betweenness regardless
of whether their score was actually nonzero. On real data, this meant a
node with betweenness=0 (a hub that talks to everyone directly, so
nothing needs to route through it) showed up in the "bridges" list
purely to pad it to 5 results — misleadingly implying it had a bridging
role it didn't have. Fixed by filtering out zero-betweenness nodes
entirely before ranking, even if that means returning fewer than top_n
results. This is a good interview example of the difference between "no
results found" and "a real zero" — a score of exactly 0 here isn't noise,
it's meaningful, and silently padding past it would have hidden that.

---

## backend/routers/analysis.py (new — Phase 8)

**Purpose:** Exposes the link analysis graph over HTTP —
`GET /analysis/{case_id}/graph` and `GET /analysis/{case_id}/key-players`.

**Important functions:**
- `get_communication_graph()` — returns the full graph as a flat
  nodes+edges JSON shape, designed to be handed directly to a graph
  visualization library (react-force-graph, vis-network, Pyvis) without
  any further transformation on the frontend.
- `get_key_players()` — returns just the top-N hubs and top-N bridges, a
  faster answer for "who matters here" without needing to render a full
  graph.
- `_build_graph_for_case()` — shared helper so both endpoints load the
  case's chats/calls and build the graph the same way exactly once.

**Why nodes+edges JSON instead of returning NetworkX's native format:**
NetworkX graph objects aren't JSON-serializable directly, and even if
they were, every graph visualization library expects the same flat
`{nodes: [...], edges: [...]}` shape — converting to that shape here
means the frontend never needs to know or care that NetworkX is involved
at all.

**Common errors and how to debug:**
- *404 "Case not found"* → wrong `case_id`.
- *Empty nodes/edges with a "message" field explaining why* → the case
  has no chat/call records with valid sender/receiver numbers; this is a
  deliberate empty-state response, not an error.

**Interview questions:**
- "Walk me through what happens when the frontend requests the graph." →
  router validates the case exists → loads chats+calls from SQLite →
  `graph_analyzer.build_communication_graph()` builds the NetworkX graph
  → `compute_centrality()` scores every node → `graph_to_json()`
  flattens it → returned directly, ready to render.

**Simple interview explanation:** "This is the endpoint that turns raw
chat and call records into a graph the frontend can actually draw —
nodes are phone numbers, edges show how strongly two people are
connected, and every node comes pre-scored with its hub/bridge
importance."


---

## backend/vector_store/chroma_store.py (fixed)

**Purpose:** Wraps ChromaDB + TF-IDF to provide semantic (meaning-based)
search over a case's chats, calls, and contacts, on top of the keyword
search that `routers/query.py` already provides.

**Important functions/classes:**
- `ForensicVectorStore` — the main class, one instance shared as a
  singleton via `get_vector_store()`.
- `index_all(case_id, chats, calls, contacts)` — builds a text document
  per record, fits a TF-IDF vectorizer on those documents, and upserts
  the resulting vectors + metadata into ChromaDB.
- `semantic_search(query, case_id, ...)` — embeds the query using that
  case's vectorizer, asks ChromaDB for the nearest vectors filtered to
  `case_id`, and returns ranked results with similarity scores.

**Bug fixed — why it mattered:** TF-IDF vectors only mean something
relative to the vocabulary they were fit on. The original code kept ONE
vectorizer for the entire app, refit every time *any* case was indexed.
So: upload Case A (vectorizer fit on A's words) → upload Case B
(vectorizer refit on B's words, A's old vectorizer overwritten) → search
Case A again → you're now embedding the query with B's vocabulary against
vectors that were stored using A's vocabulary. Results become meaningless,
silently, with no error. The fix: one vectorizer file per `case_id`
(`vectorizers/tfidf_vectorizer_{case_id}.pkl`), loaded on demand and
cached in memory.

**Why this design (TF-IDF + per-case fitting) instead of sentence-transformers:**
TF-IDF needs no model download and works fully offline — good for a tool
that might run in an air-gapped forensic lab. The tradeoff is that each
case needs its own fitted vectorizer, since TF-IDF's vector space depends
on the corpus. sentence-transformers wouldn't have this problem (its
embedding space is fixed/pretrained, shared across all cases automatically)
— that's the honest "what I'd upgrade to in production" answer.

**Common errors and how to debug:**
- *Semantic search returns 0 results for a case that should have data* →
  check `GET /search/{case_id}/index-status`; if `chromadb_indexed` is 0,
  call `POST /search/{case_id}/reindex`.
- *`RuntimeError: Vectorizer not fitted`* (old behavior, now returns `[]`
  instead) → means `index_all` was never called for that case_id, or its
  vectorizer file was deleted/corrupted.

**Interview questions:**
- "Why did search results for one case start looking wrong after you
  uploaded a second case?" → explain the vectorizer-collision bug and fix,
  exactly as above. This is a great real bug-found-and-fixed story.
- "Why not just use one global vectorizer fit on everything?" → would
  require refitting (and re-embedding every existing case) on every new
  upload, which doesn't scale and makes old embeddings stale mid-flight.

**Simple interview explanation:** "Each case gets its own TF-IDF model and
its own saved vectorizer file, so uploading a new case never messes up
search for an older one. I found and fixed this as a real bug during a
code review — originally there was just one shared vectorizer for the
whole app."

---

## backend/ai/query_engine.py (new)

**Purpose:** The RAG (Retrieve-Augment-Generate) glue layer. Connects
`chroma_store.py` (retrieval) to `llm_client.py` (generation) without
either of them knowing about the other.

**Important functions:**
- `ask_question(case_id, question, ...)` — retrieves top-K relevant
  evidence via `semantic_search`, builds a numbered context block, asks
  the LLM client to answer using only that context, and returns the
  answer plus the exact source records used.
- `_build_context(evidence)` — formats retrieved records into a numbered
  text block (`[1] (chat, risk=4.5) ...`) that both the LLM and a human
  reviewer can read.

**Why this file exists as its own module:** Keeping retrieval and
generation decoupled means either one can be swapped independently —
e.g. switching from TF-IDF to sentence-transformers later only touches
`chroma_store.py`; switching from Gemini to Claude only touches
`llm_client.py`. `query_engine.py` is the only place that needs to know
both exist.

**Code flow:** question → `chroma_store.semantic_search()` → list of
evidence dicts → `_build_context()` → numbered string → `LLMClient.ask()`
→ `{answer, mode}` → combined with the source list → returned to the
router.

**Common errors and how to debug:**
- *Answer says "No relevant evidence was found"* → either the case isn't
  indexed yet, or the question's wording doesn't share TF-IDF vocabulary
  with anything in the case (a real limitation of TF-IDF vs. true semantic
  embeddings — worth mentioning in interviews as a known tradeoff).

**Interview questions:**
- "How do you prevent the LLM from making things up?" → this file is the
  answer: it never lets the LLM see anything except retrieved evidence,
  and the system prompt explicitly instructs it to say so if the evidence
  is insufficient. The response also includes the literal source records,
  so a human can verify every claim.
- "Why separate this from llm_client.py?" → single-responsibility:
  llm_client.py only knows how to talk to an LLM provider; query_engine.py
  only knows how to combine retrieval with generation. Neither needs to
  change if the other does.

**Simple interview explanation:** "This file is the actual RAG pipeline —
it pulls the most relevant evidence for a question, hands it to the LLM
with strict instructions to only use that evidence, and returns the
answer along with the exact records it was based on."

---

## backend/routers/ai.py (new)

**Purpose:** Exposes the RAG pipeline as an HTTP API — `POST
/ai/{case_id}/ask` and `GET /ai/mode`.

**Important functions:**
- `ask(case_id, request, db)` — validates the case is ready, calls
  `query_engine.ask_question()`, returns the result.
- `get_ai_mode()` — reports whether Gemini/OpenAI/offline mode is active,
  so the frontend can show the officer what kind of answer they're getting.

**Why this needed to be created:** `llm_client.py` already existed with a
complete fallback chain, but nothing in the API layer ever called it —
there was no route. This was the single missing piece between "the AI
logic is written" and "an officer can actually ask a question through the
API."

**Common errors and how to debug:**
- *404 "Case not found"* → wrong `case_id`, or case was deleted.
- *400 "Case not ready"* → still processing; check `GET
  /upload/case/{id}/status` first.
- *400 "Question cannot be empty"* → client-side validation should prevent
  this, but the API rejects it defensively too.

**Interview questions:**
- "Walk me through what happens when an officer submits a question." →
  POST hits this router → validates case status → calls
  `query_engine.ask_question()` → that retrieves evidence from ChromaDB →
  builds context → calls the LLM client → returns answer + sources →
  router adds `case_id`/`question` back into the response and returns it.

**Simple interview explanation:** "This is the actual endpoint officers
hit to ask a question — it just validates the case is ready, then hands
off to the RAG pipeline and returns whatever it gives back."

---

## backend/ai/llm_client.py (fixed)

**Purpose:** Unchanged from original design — unified wrapper with a
Gemini → OpenAI → offline fallback chain — but with one real bug fixed.

**Bug fixed:** `ask()` defaulted `system_prompt=""`. The OpenAI path had
its own internal fallback (`system_prompt or FORENSIC_SYSTEM_PROMPT`), but
the Gemini path didn't — it just inserted whatever was passed in directly.
Since callers were never actually passing the system prompt explicitly,
every Gemini-mode answer would have skipped the "answer ONLY from this
evidence" grounding instruction. Fixed by defaulting it inside `ask()`
itself, so it's guaranteed for every provider, not just one.

**Why this bug mattered:** Grounding is the entire point of building RAG
for a forensic tool instead of just calling an LLM directly. A silently
ungrounded Gemini response defeats that purpose without any visible error
— it would just look like a normal answer, possibly hallucinated.

**Interview questions:**
- "How did you make sure the grounding instruction was actually being
  used?" → good chance to mention this exact bug as something you caught
  during review, not something you got right by luck the first time.

---

## Real-world validation: Gemini model deprecation (encountered during testing)

**What happened:** While testing `/ai/{case_id}/ask` with a real Gemini API
key, the call failed with `404 models/gemini-1.5-flash is not found for API
version v1beta`. Google had deprecated and shut down all Gemini 1.0 and 1.5
models. Fixed by updating `GEMINI_MODEL` in `config.py` from
`"gemini-1.5-flash"` to `"gemini-2.5-flash"`.

**Why this is worth mentioning in an interview, not hiding:** This wasn't a
bug in the code — it was an external API changing under a hardcoded model
name. What's actually interesting is what happened when it failed: the
system didn't crash or return a 500 error. `llm_client.py`'s exception
handler caught the failure and fell back to the offline evidence summary
automatically, with the actual error message included in the response
(`"⚠️ Note: AI summarization unavailable (404 ...)"`). The officer using
the tool would have still gotten a usable answer, not a blank screen.

**Interview question this answers:** "How does your system handle a
third-party API outage or deprecation?" → "It already has — a Gemini model
I was using got deprecated mid-development, and the fallback chain caught
it and degraded to a structured offline summary automatically, with the
real error surfaced for debugging. That's exactly the failure mode the
fallback design exists for."

**Lesson for config design:** Hardcoding a specific model version string
(vs. an alias the provider keeps pointed at a current model) means you
inherit the provider's deprecation schedule. Worth tracking
https://ai.google.dev/gemini-api/docs/changelog periodically, or pinning to
whichever alias Google documents as their "current stable" pointer if one
exists at the time you read this.

---

## Follow-up fix: truncated answers (token limit + prompt verbosity)

**What happened:** A real Gemini-mode test with 9 matching crypto-related
records got cut off mid-sentence. Root cause was two compounding factors:
1. `MAX_RESPONSE_TOKENS` was 2048, and
2. the prompt asked the model to "cite specific messages... when possible"
   without limiting *how many* it should enumerate — so it tried to write
   a full structured breakdown for every one of the 9 records and ran out
   of budget partway through.

**Fix (both, deliberately):**
- Raised `MAX_RESPONSE_TOKENS` to 3072 in `config.py` — a safety margin,
  not the actual fix.
- Rewrote the Gemini prompt in `llm_client.py` to explicitly ask for a
  short direct answer up front, grouped/summarized evidence instead of one
  block per record, `[N]`-style index citations instead of re-quoting full
  records, and a representative-sample approach once there are more than
  ~5 matching records.

**Why both and not just one:** Raising the token limit alone just delays
the same problem to a larger evidence set (e.g. 50 matching records
instead of 9). Tightening the prompt alone reduces *typical* verbosity but
doesn't guarantee safety against an unusually large or repetitive case.
Together, the prompt keeps normal answers naturally concise, and the token
increase is headroom for when there's genuinely a lot to summarize.

**Interview question this answers:** "How do you handle cases with a large
volume of matching evidence without blowing your token budget or
overwhelming the officer with a wall of text?" → explain this exact
grouped-summary + indexed-citation approach, and that you found the
verbosity problem through real testing, not by guessing upfront.

**Note:** This prompt change currently only applies to the Gemini code
path (`_ask_gemini`). The OpenAI fallback path builds its own simpler
prompt and wasn't updated to match — a known asymmetry, low priority since
OpenAI is the secondary fallback, but worth aligning if OpenAI becomes the
primary provider later.