<div align="center">

# 🔍 AI-Based UFDR Forensic Intelligence Platform

### Evidence-grounded RAG for digital forensic investigations

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-FF6B6B?style=for-the-badge)](https://trychroma.com)
[![Gemini](https://img.shields.io/badge/Gemini_2.5-RAG_Q%26A-4285F4?style=for-the-badge&logo=googlegemini&logoColor=white)](https://ai.google.dev)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)

**An AI tool that ingests UFDR (Universal Forensic Extraction Device Report) data from seized devices, lets investigators ask plain-English questions, and returns answers that cite the exact evidence they're based on — never just "the AI's word for it."**

Built against a real Smart India Hackathon problem statement — **Ministry of Home Affairs / National Investigation Agency, Problem ID 25198.**

[Features](#-features) • [Live Demo](#-live-demo) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [API Docs](#-api-endpoints) • [Why This Matters](#-why-this-project-matters)

---

> ⚠️ **Disclaimer:** This tool assists qualified forensic examiners — it does not replace them.
> All AI-generated findings must be verified by a certified examiner before use in any proceeding.
> Built and tested entirely on **synthetic sample data** — no real case data is used at any stage.

</div>

---

## 🎯 What This Tool Does

A seized smartphone can hold 100,000+ messages, tens of thousands of calls,
and thousands of contacts. Reviewing that manually can take an investigator
weeks. This tool cuts that down to minutes:

| Capability | What It Does | Status |
|---|---|:---:|
| 📁 **UFDR Ingestion** | Parses JSON / ZIP / CSV forensic exports, normalizes inconsistent field names | ✅ |
| 🔍 **Entity Extraction** | Detects crypto addresses (BTC/ETH/TRON), foreign phone numbers, suspicious keywords | ✅ |
| ⚠️ **Risk Scoring** | Auto-scores every chat/call/contact 0–10 based on detected entities | ✅ |
| 🧠 **Semantic Search** | Finds records by *meaning*, not just exact keyword match | ✅ |
| 💬 **Evidence-Grounded Q&A** | Ask a question in plain English, get an answer **with cited source records** | ✅ |
| 🔁 **Resilient AI Fallback** | Gemini → OpenAI → offline structured summary — never just breaks | ✅ |
| 🕸️ **Basic Link Analysis** | Find common contacts shared between two suspects | ✅ |
| 🕸️ **Full Relationship Graph** | NetworkX graph (chats+calls combined), degree + betweenness centrality to find hubs and bridges | ✅ |
| 📊 **Risk Pattern Detection** | Case-level suspicious pattern detection beyond per-record scoring | 🔜 |
| 📄 **PDF Reports** | Auto-generated investigation summary documents | 🔜 |
| 🖥️ **Officer Dashboard** | Streamlit frontend | 🔜 |
| 🐳 **Docker Deployment** | Containerized, cloud-deployable | 🔜 |

## ⭐ Why This Project Matters

This isn't a generic "chatbot over documents" demo. Every AI-generated
answer is grounded in retrieved evidence and returns the exact source
records it used — because in an investigative context, "the AI said so"
can never be the final word. That single constraint shapes the whole
system: retrieval before generation, structured evidence linking, and a
fallback chain that keeps the tool useful even with zero API keys
configured.

## 💬 Live Demo — Real Output

**Question:** *"Is there any evidence of cryptocurrency transactions?"*

> Yes, there is clear evidence of cryptocurrency transactions. Several
> messages across Telegram, WhatsApp, and SMS reference sending funds to
> two distinct addresses: a Bitcoin Bech32 address (`BC1qar0s...`) [1][2][3][4][5]
> and a Bitcoin Legacy address (`1A1zP1...`) requesting 0.5 BTC [6][7][8][9].
> Several of these messages involve foreign numbers (UAE, UK)...

— powered by Gemini 2.5 Flash, grounded in 15 retrieved evidence records,
every claim traceable to a specific `record_id` in the response.

## 🛠 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **API Framework** | FastAPI | Async, auto-generates `/docs`, type-safe via Pydantic |
| **Database** | SQLite → PostgreSQL | Zero local setup; SQLAlchemy keeps the same code portable |
| **ORM** | SQLAlchemy 2.0 | Database-agnostic, prevents SQL injection |
| **Vector Store** | ChromaDB | Offline, file-based, cosine similarity |
| **Embeddings** | TF-IDF (scikit-learn), **per-case scoped** | No model download needed; each case gets its own fitted vectorizer so multiple cases never corrupt each other's search results — a real bug found and fixed during review |
| **Entity Extraction** | Regex (crypto, phones, emails, keywords) | Deterministic, near-100% accurate for structured patterns |
| **LLM** | Gemini 2.5 Flash → OpenAI → offline fallback | Free tier; the tool degrades gracefully instead of breaking if a model is deprecated or a key is missing — verified live when Gemini 1.5 was retired mid-development |
| **Graph Analysis** | NetworkX *(planned)* | Pure Python, no extra service |
| **Frontend** | Streamlit *(planned)* | Fast to ship, good for data-heavy dashboards |
| **Reports** | ReportLab *(planned)* | Standard Python PDF generation |

**A deliberate, explainable tradeoff:** TF-IDF needs no model download and
runs fully offline — appropriate for a forensic tool that may need to run
air-gapped. Its cost is that the vector space depends on the corpus it's
fit on, so this project gives **every case its own vectorizer** rather than
sharing one globally. In production, swapping to `sentence-transformers`
would remove that constraint entirely, since its embedding space is fixed
and shared across cases.

## 🏗 Architecture

```
Upload (JSON/ZIP/CSV) → Parser → Entity Extractor → SQLite (SQLAlchemy)
                                        │
                                        ▼
                          ChromaDB (per-case TF-IDF vectors)
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
      SQL keyword search        Semantic search             RAG Q&A
        (query.py)                (search.py)          (ai.py + query_engine.py)
                                                                │
                                                                ▼
                                                  LLMClient (Gemini → OpenAI → offline)
```

**RAG flow in detail:** question → top-K relevant records retrieved from
ChromaDB (scoped to that case only) → numbered evidence context built →
LLM instructed to answer **using only that context**, citing record
indices → response returns the answer **plus the literal source records**,
so every claim can be checked against real data.

Full diagrams: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 📁 Project Structure

```
ufdr-analyzer/
├── backend/
│   ├── main.py                       # FastAPI app entry point
│   ├── config.py                     # Settings from .env
│   ├── database.py                   # SQLAlchemy engine + session
│   ├── models.py                     # Case, ChatMessage, CallRecord, Contact, MediaFile
│   ├── parsers/ufdr_parser.py        # JSON/ZIP/CSV → normalized records
│   ├── extractors/entity_extractor.py # Regex entity extraction + risk scoring
│   ├── vector_store/chroma_store.py   # ChromaDB + per-case TF-IDF
│   ├── ai/
│   │   ├── llm_client.py             # Gemini/OpenAI/offline LLM wrapper
│   │   └── query_engine.py           # RAG pipeline (retrieve → context → generate)
│   ├── analysis/                     # 🔜 NetworkX link analysis
│   ├── reports/                      # 🔜 PDF report generation
│   └── routers/
│       ├── upload.py                 # File ingestion + background processing
│       ├── query.py                  # SQL keyword search + common-contact link analysis
│       ├── search.py                 # Semantic search
│       └── ai.py                     # Natural language Q&A (RAG)
├── data/
│   ├── sample_ufdr/                  # Synthetic test data + generator
│   └── uploads/                      # Uploaded case files (gitignored)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROJECT_TRACKER.md            # Live status — what's actually done
│   ├── LEARNING_NOTES.md             # Per-file explanations, interview prep
│   ├── INTERVIEW_QA.md
│   └── screenshots/
├── requirements.txt
├── .env.example
└── README.md
```

## ⚡ Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/YOUR_USERNAME/ufdr-analyzer.git
cd ufdr-analyzer

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Add GEMINI_API_KEY to .env for AI-powered answers — free key at
# https://aistudio.google.com/app/apikey
# (Optional — the tool works without it, falling back to a structured
# offline evidence summary instead of an AI-written answer.)

# 5. Generate sample data (if not already present)
python data/sample_ufdr/generate_sample_data.py

# 6. Start the backend
uvicorn backend.main:app --reload --port 8000
```

Visit **http://localhost:8000/docs** for the interactive Swagger API explorer.

## 📖 How to Use

1. **Upload a case:** `POST /upload/case` → upload `data/sample_ufdr/sample_case_001.json`
2. **Check status:** `GET /upload/case/{case_id}/status` → wait for `"ready"`
3. **Keyword search:** `GET /query/{case_id}/chats/search?q=bitcoin`
4. **Semantic search:** `POST /search/{case_id}/semantic` → `{"query": "cryptocurrency transfer"}`
5. **Ask a question:** `POST /ai/{case_id}/ask` → `{"question": "Is there evidence of crypto transactions?"}`
   → returns an answer **and** the exact evidence records it's based on.

## 📡 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload/case` | Upload UFDR file, background processing |
| `GET` | `/upload/case/{id}/status` | Check processing status |
| `GET` | `/query/{id}/chats/search` | Keyword search with filters |
| `GET` | `/query/{id}/contacts/common` | Common contacts between two numbers (basic link analysis) |
| `POST` | `/search/{id}/semantic` | Meaning-based search |
| `POST` | **`/ai/{id}/ask`** | **Natural language Q&A — evidence-grounded, citation-backed** |
| `GET` | `/ai/mode` | Check whether Gemini / OpenAI / offline mode is active |
| `GET` | `/analysis/{id}/graph` | Full communication graph (nodes+edges), ready for visualization |
| `GET` | `/analysis/{id}/key-players` | Top hubs (degree centrality) and top bridges (betweenness centrality) |

Full interactive list at `/docs` once the server is running.

## 📈 Scalability Plan

| Component | Current | Production Path |
|---|---|---|
| Database | SQLite | PostgreSQL (SQLAlchemy makes this a config change, not a rewrite) |
| Vector Store | ChromaDB, per-case TF-IDF | Qdrant + sentence-transformers |
| Background Jobs | FastAPI BackgroundTasks | Celery + Redis |
| File Storage | Local disk | S3-compatible object storage |
| Auth | None yet | JWT + role-based access (officer / admin) |

## 🎓 Resume Bullet Points

- Built a forensic intelligence platform enabling natural-language evidence
  search over structured data via an evidence-grounded RAG pipeline
  (FastAPI, ChromaDB, Gemini), where every AI answer cites the exact source
  records it was based on.
- Designed a per-case vector search scheme to keep multi-case search
  results isolated; identified and fixed a vectorizer-sharing bug during
  code review that was silently corrupting cross-case search results.
- Built a fallback-chain LLM client (Gemini → OpenAI → offline structured
  summary) that kept the tool fully functional through a real Gemini model
  deprecation encountered mid-development — validating the resilience
  design under an actual production failure, not just a hypothetical one.
- Built and tested against a real Ministry of Home Affairs / National
  Investigation Agency smart-automation problem statement (SIH, Problem ID 25198).

## 🗣 Interview Explanation (30-second version)

"I built a tool for digital forensic investigators that ingests phone
extraction reports and lets them ask plain-English questions about a case
instead of manually scrolling through thousands of records. Every answer
is grounded in retrieved evidence and returns the specific source records
it used — nothing is just taken on the AI's word. It falls back
gracefully through Gemini, then OpenAI, then a structured offline summary,
so it never just breaks — which I actually validated for real when a
Gemini model I was using got deprecated mid-project and the fallback
caught it cleanly. Stack is FastAPI, ChromaDB with per-case TF-IDF for
search, and SQLAlchemy over SQLite."

## 🤝 Contributing

Student project built for learning and portfolio purposes. Issues and PRs
around entity extraction patterns, additional UFDR format support, or the
planned graph/reporting phases are welcome.

## 📄 License

For educational and research purposes only. Not intended for production
forensic use without independent validation by qualified examiners.

---

<div align="center">

**Live status, known issues, and what's next:** [`docs/PROJECT_TRACKER.md`](docs/PROJECT_TRACKER.md)

*Built for digital forensics education — based on SIH Problem Statement ID 25198.*

</div>