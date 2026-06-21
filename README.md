<div align="center">

# 🔍 UFDR Forensic Analysis Tool

### AI-powered Digital Forensics Assistant

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-FF6B6B?style=for-the-badge)](https://trychroma.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)

**Assists digital forensic investigators in analyzing UFDR reports from seized devices using AI-powered search, entity extraction, and evidence summarization.**

[Features](#-features) • [Quick Start](#-quick-start) • [API Docs](#-api-endpoints) • [Architecture](#-architecture) • [Progress](#-development-progress) • [Deployment](#-deployment)

---

> ⚠️ **Disclaimer:** This tool is designed to *assist* qualified forensic examiners — not replace them.
> All AI-generated findings must be verified by a certified digital forensic expert.
> For authorized use only.

</div>

---

## 📋 Table of Contents

- [What This Tool Does](#-what-this-tool-does)
- [Development Progress](#-development-progress)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [How to Use](#-how-to-use)
- [API Endpoints](#-api-endpoints)
- [Architecture](#-architecture)
- [Deployment](#-deployment)
- [Scalability](#-scalability)

---

## 🎯 What This Tool Does

A seized smartphone can contain **100,000+ messages, 50,000+ calls, and thousands of contacts**.
A forensic investigator reading this manually could take **weeks**.

This tool reduces that to **minutes** by:

| Capability | What It Does |
|-----------|-------------|
| 📁 **File Ingestion** | Parses UFDR exports (JSON, ZIP, CSV) from tools like Cellebrite |
| 🔍 **Entity Extraction** | Auto-detects Bitcoin addresses, foreign phone numbers, suspicious keywords |
| ⚠️ **Risk Scoring** | Assigns every record a 0–10 risk score automatically |
| 🧠 **Semantic Search** | Finds messages by *meaning*, not just exact keywords |
| 💬 **Natural Language Q&A** | Ask questions like *"show me all crypto transfers"* |
| 🕸️ **Link Analysis** | Maps who communicates with whom (graph visualization) |
| 📄 **Evidence Reports** | Generates downloadable PDF investigation summaries |

---

## 🚀 Development Progress

```
Phase 1 ████████████████████ 100% ✅  File parsing + Entity extraction + SQL search
Phase 2 ████████████████████ 100% ✅  ChromaDB vector store + Semantic search
Phase 3 ░░░░░░░░░░░░░░░░░░░░   0% 🔜  Gemini AI natural language Q&A (RAG)
Phase 4 ░░░░░░░░░░░░░░░░░░░░   0% 🔜  Streamlit frontend dashboard
Phase 5 ░░░░░░░░░░░░░░░░░░░░   0% 🔜  NetworkX communication graph analysis
Phase 6 ░░░░░░░░░░░░░░░░░░░░   0% 🔜  PDF evidence report generation
Phase 7 ░░░░░░░░░░░░░░░░░░░░   0% 🔜  Docker + cloud deployment
```

### ✅ Phase 1 — Completed
- [x] Upload UFDR files (JSON, ZIP, CSV formats)
- [x] Parse chats, calls, contacts, media metadata
- [x] Regex-based entity extraction (Bitcoin, Ethereum, TRON, phone numbers)
- [x] Automatic risk scoring (0–10 scale)
- [x] Foreign number detection (UAE, UK, USA, Pakistan, etc.)
- [x] Suspicious keyword flagging (30+ keywords)
- [x] SQLite structured storage with SQLAlchemy ORM
- [x] Background file processing (non-blocking API)
- [x] REST API with 10+ endpoints
- [x] Synthetic UFDR data generator (189 realistic records)
- [x] Interactive API docs at `/docs`

### ✅ Phase 2 — Completed
- [x] ChromaDB persistent vector store
- [x] TF-IDF embeddings (works offline, no API key needed)
- [x] Semantic similarity search across chats, calls, contacts
- [x] "Find similar records" endpoint
- [x] Re-indexing endpoint
- [x] Index status monitoring
- [x] Automatic indexing after file upload

### 🔜 Phase 3 — Gemini AI Q&A (Next)
- [ ] Gemini 1.5 Flash integration
- [ ] RAG pipeline (retrieve → augment → generate)
- [ ] Natural language answers with cited evidence
- [ ] Keyword fallback when API key is absent

### 🔜 Phase 4 — Streamlit Dashboard
- [ ] File upload interface
- [ ] Case management panel
- [ ] Search results with highlighted entities
- [ ] Risk score visualization

### 🔜 Phase 5 — Graph Analysis
- [ ] NetworkX communication graph
- [ ] Suspect link visualization (Pyvis)
- [ ] Common contact detection
- [ ] Timeline view

### 🔜 Phase 6 — PDF Reports
- [ ] Auto-generated evidence summaries
- [ ] Top risk messages
- [ ] Entity highlight report
- [ ] Chain of custody info

### 🔜 Phase 7 — Deployment
- [ ] Dockerfile + docker-compose
- [ ] Render / Railway deployment guide
- [ ] Environment variable management
- [ ] JWT authentication

---

## 🛠 Tech Stack

| Layer | Technology | Version | Why |
|-------|-----------|---------|-----|
| **API Framework** | FastAPI | 0.111 | Async, auto-generates `/docs`, type-safe |
| **Database** | SQLite → PostgreSQL | — | Zero setup locally; same code works on Postgres |
| **ORM** | SQLAlchemy | 2.0 | Database-agnostic, prevents SQL injection |
| **Vector Store** | ChromaDB | 1.5 | Offline, file-based, cosine similarity |
| **Embeddings** | TF-IDF (sklearn) | — | No download needed, weights rare forensic terms |
| **Entity Extraction** | Regex + spaCy | — | 100% reliable for structured patterns |
| **LLM** | Gemini 1.5 Flash | — | Free tier, generous context window *(Phase 3)* |
| **Graph Analysis** | NetworkX | 3.3 | Pure Python, no external service *(Phase 5)* |
| **Frontend** | Streamlit | 1.35 | Ships in hours, great for data dashboards *(Phase 4)* |
| **Reports** | ReportLab | 4.2 | Industry standard Python PDF *(Phase 6)* |
| **Validation** | Pydantic | 2.7 | Type safety, automatic request validation |

---

## 📁 Project Structure

```
ufdr-analyzer/
│
├── 📂 backend/                    # FastAPI backend
│   ├── 📄 main.py                 # App entry point, startup, routers
│   ├── 📄 config.py               # All settings — reads from .env
│   ├── 📄 database.py             # SQLAlchemy engine + session management
│   ├── 📄 models.py               # Database table definitions (5 tables)
│   │
│   ├── 📂 parsers/
│   │   └── 📄 ufdr_parser.py      # Reads JSON/ZIP/CSV UFDR files
│   │
│   ├── 📂 extractors/
│   │   └── 📄 entity_extractor.py # Regex: crypto, phones, keywords, risk score
│   │
│   ├── 📂 vector_store/           # ✅ Phase 2
│   │   └── 📄 chroma_store.py     # ChromaDB + TF-IDF semantic search
│   │
│   ├── 📂 ai/                     # 🔜 Phase 3
│   │   ├── 📄 llm_client.py       # Gemini/OpenAI wrapper
│   │   └── 📄 query_engine.py     # RAG pipeline
│   │
│   ├── 📂 analysis/               # 🔜 Phase 5
│   │   └── 📄 graph_analyzer.py   # NetworkX link analysis
│   │
│   ├── 📂 reports/                # 🔜 Phase 6
│   │   └── 📄 report_generator.py # PDF generation
│   │
│   └── 📂 routers/
│       ├── 📄 upload.py           # POST /upload/case — file ingestion
│       ├── 📄 query.py            # GET /query — SQL keyword search
│       └── 📄 search.py           # POST /search — semantic search ✅ Phase 2
│
├── 📂 frontend/                   # 🔜 Phase 4
│   └── 📄 app.py                  # Streamlit dashboard
│
├── 📂 data/
│   ├── 📂 sample_ufdr/
│   │   ├── 📄 generate_sample_data.py   # Creates synthetic test data
│   │   └── 📄 sample_case_001.json      # 189-record synthetic UFDR case
│   └── 📂 uploads/                # Uploaded case files (gitignored)
│
├── 📂 sqlite_db/                  # SQLite database (gitignored)
├── 📂 vector_db/                  # ChromaDB vectors (gitignored)
│
├── 📄 requirements.txt
├── 📄 .env.example
├── 📄 .gitignore
├── 📄 Dockerfile                  # 🔜 Phase 7
├── 📄 docker-compose.yml          # 🔜 Phase 7
├── 📄 README.md                   # ← You are here
└── 📄 PROJECT_EXPLANATION.md      # Deep learning guide
```

---

## ⚡ Quick Start

### Prerequisites
- Python **3.10 or higher**
- pip

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/ufdr-analyzer.git
cd ufdr-analyzer
```

### 2. Create virtual environment
```bash
python -m venv venv

# Activate (choose your OS):
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 4. Configure environment
```bash
cp .env.example .env
# Open .env and add your GEMINI_API_KEY (optional for Phase 1 & 2)
# Free key: https://aistudio.google.com/app/apikey
```

### 5. Generate sample data
```bash
python data/sample_ufdr/generate_sample_data.py
```
Output:
```
✅ Generated: data/sample_ufdr/sample_case_001.json
   📱 Chat messages: 100
   📞 Call records:  50
   👤 Contacts:      9
   🖼️  Media files:   30
```

### 6. Start the backend
```bash
uvicorn backend.main:app --reload --port 8000
```
Output:
```
🚀 Starting UFDR Forensic Analysis Tool v1.0.0
✅ Database tables created/verified.
✅ Vector store ready.
✅ App ready → http://localhost:8000/docs
```

### 7. Open API Explorer
Visit **http://localhost:8000/docs** — interactive Swagger UI to test all endpoints.

---

## 📖 How to Use

### Upload a case
1. Go to `http://localhost:8000/docs`
2. Click **POST /upload/case** → **Try it out**
3. Upload `data/sample_ufdr/sample_case_001.json`
4. Copy the returned `case_id`

### Check processing status
```
GET /upload/case/{case_id}/status
```
Wait until `"status": "ready"`.

### Run a semantic search *(Phase 2)*
```json
POST /search/{case_id}/semantic
{
  "query": "cryptocurrency bitcoin transfer wallet",
  "record_type": "chat",
  "n_results": 10
}
```

### Run keyword searches *(Phase 1)*
```
GET /query/{case_id}/chats/search?q=delivery&min_risk=2
GET /query/{case_id}/chats/crypto
GET /query/{case_id}/calls/foreign
GET /query/{case_id}/contacts/common?number_a=+919876543210&number_b=+919988776655
GET /query/{case_id}/summary
```

---

## 📡 API Endpoints

### 📤 Upload
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload/case` | Upload UFDR file, start background processing |
| `GET` | `/upload/case/{id}/status` | Check processing status |
| `GET` | `/upload/cases` | List all cases with record counts |
| `DELETE` | `/upload/case/{id}` | Delete a case and all its data |

### 🔎 Keyword Search (Phase 1)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/query/{id}/chats/search?q=...` | Keyword search with filters |
| `GET` | `/query/{id}/chats/crypto` | Pre-built: all crypto-related chats |
| `GET` | `/query/{id}/calls/foreign` | Pre-built: foreign number calls |
| `GET` | `/query/{id}/contacts/common` | Common contacts between two suspects |
| `GET` | `/query/{id}/summary` | Case statistics dashboard |

### 🧠 Semantic Search (Phase 2)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/search/{id}/semantic` | Meaning-based search (TF-IDF) |
| `GET` | `/search/{id}/similar/{record_id}` | Find records similar to a specific one |
| `GET` | `/search/{id}/index-status` | Check ChromaDB indexing status |
| `POST` | `/search/{id}/reindex` | Re-index case into ChromaDB |

### 🤖 Natural Language Q&A (Phase 3 — Coming)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/ai/{id}/ask` | Ask natural language questions |
| `POST` | `/ai/{id}/summarize` | Generate case summary |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    OFFICER'S BROWSER                     │
│              http://localhost:8501 (Streamlit)           │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP requests
┌────────────────────────▼────────────────────────────────┐
│                  FASTAPI BACKEND :8000                   │
│                                                          │
│  POST /upload/case                                       │
│    └─► UFDRParser → EntityExtractor → SQLite            │
│    └─► index_all() → ChromaDB (Phase 2)                 │
│                                                          │
│  GET /query/{id}/chats/search                           │
│    └─► SQLAlchemy SQL query → results                   │
│                                                          │
│  POST /search/{id}/semantic                             │
│    └─► TF-IDF embed query → ChromaDB cosine search      │
│    └─► Enrich with full SQLite records → results        │
│                                                          │
│  POST /ai/{id}/ask  (Phase 3)                           │
│    └─► ChromaDB top-K retrieval                         │
│    └─► Gemini LLM with evidence context → answer        │
└──────────┬─────────────────┬───────────────────────────┘
           │                 │
    ┌──────▼──────┐   ┌──────▼──────┐
    │   SQLite     │   │  ChromaDB   │
    │  (records)   │   │  (vectors)  │
    └─────────────┘   └─────────────┘
```

---

## 🌐 Deployment

### Local (Current)
```bash
uvicorn backend.main:app --reload --port 8000
streamlit run frontend/app.py          # Phase 4
```

### Docker (Phase 7)
```bash
docker-compose up --build
# Backend:  http://localhost:8000
# Frontend: http://localhost:8501
```

### Free Cloud Options
| Platform | What | How |
|----------|------|-----|
| **Render** | Backend (FastAPI) | Connect GitHub → auto-deploy |
| **Railway** | Backend + PostgreSQL | One-click deploy + DB add-on |
| **Hugging Face Spaces** | Frontend (Streamlit) | Push to HF repo, free tier |

---

## 📈 Scalability

| Component | Prototype | Production |
|-----------|-----------|------------|
| Database | SQLite | PostgreSQL |
| Vector Store | ChromaDB (local) | Qdrant / Pinecone |
| Background Jobs | FastAPI BackgroundTasks | Celery + Redis |
| File Storage | Local disk | AWS S3 / GCS |
| Embeddings | TF-IDF (offline) | sentence-transformers |
| Auth | None | JWT + Role-based access |

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 🤝 Contributing

This is a student project for educational purposes.
Pull requests welcome for improvements to entity extraction patterns,
additional UFDR format support, or UI enhancements.

---

## 📄 License

For educational and research purposes only.
Not intended for production forensic use without proper validation.

---

<div align="center">

**Built with ❤️ for digital forensics education**

*If this helped you, give it a ⭐ on GitHub*

</div>