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