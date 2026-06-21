# Interview Q&A

> Populated incrementally as each phase is built. Phase 0 covers conceptual /
> system-design questions you can already answer before writing any code.

## System Design & Problem Understanding

**Q: Walk me through what this project does.**
A: Investigating officers get a forensic data dump from a seized phone
(UFDR-style export) containing chats, calls, contacts, media, and locations.
Manually searching through this is slow. My system ingests that data,
structures it into a database, lets the officer ask plain-English questions
and get evidence-grounded answers via RAG, builds a relationship graph
between contacts to show who talked to whom and how often, and flags
suspicious patterns with a risk score — then auto-generates a report.

**Q: Why is this harder than "just use ChatGPT on the data"?**
A: Three reasons. First, evidence traceability — a court-facing tool can't
just have an LLM assert facts; every claim must point to a specific source
record, so this is fundamentally a retrieval problem with the LLM doing
summarization, not fact generation. Second, scale — real UFDRs can have
hundreds of thousands of records, so naive "paste it all in the prompt"
doesn't work; you need chunking, embeddings, and selective retrieval. Third,
structure — calls, chats, and locations are relational data with timestamps
and entity relationships; a graph/relational layer captures things (who
called whom, when) that pure text search can't.

**Q: Why did you choose this scope (MVP → Advanced → Polish) instead of
building everything at once?**
A: Time-boxing forced me to decide what actually demonstrates skill versus
what's just more checkboxes. I went deep on RAG grounding and graph-based
link analysis because those are the technically interesting, defensible
parts — the frontend and deployment matter for presentation but aren't where
the hard problems are.

## Tech Stack Justification

**Q: Why ChromaDB instead of Pinecone or Qdrant?**
A: ChromaDB runs in-process with no extra service to deploy, which kept the
MVP simple. I designed the embedding/retrieval logic behind a service
interface so swapping in Qdrant for a managed, horizontally-scalable
deployment is a backend change, not an architecture change — that's
documented in my scalability plan.

**Q: Why local embeddings (sentence-transformers) instead of OpenAI/Gemini
embeddings?**
A: Two reasons. Practically, it's free and has no rate limits during
development. More importantly for this specific domain: forensic data is
sensitive, so keeping embedding computation local instead of sending raw
chat content to a third-party embedding API is the more defensible design
for a real investigative tool.

**Q: Why NetworkX instead of Neo4j for the relationship graph?**
A: NetworkX runs in-process and needs no extra infrastructure, which fit the
MVP's scope and the sample data size. For production scale — millions of
contacts/edges across many cases — I'd migrate to Neo4j for proper graph
indexing and Cypher query performance. I made that tradeoff deliberately and
documented it rather than over-engineering the MVP.

**Q: Why SQLite first and not PostgreSQL from day one?**
A: SQLite removes setup friction during development. Because I used
SQLAlchemy as the ORM layer, the schema is database-agnostic, so migrating
to PostgreSQL for production is a connection-string and minor dialect change,
not a rewrite — and I document that migration step explicitly.

## (Sections to fill in as built: FastAPI, SQL schema design, vector search
internals, RAG prompt design, embeddings, entity extraction, link analysis
algorithms, risk scoring logic, Docker, deployment, security.)
