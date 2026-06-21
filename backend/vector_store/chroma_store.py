"""
chroma_store.py — ChromaDB + TF-IDF semantic search (offline, no API keys needed).

KEY DESIGN:
  - One TF-IDF vectorizer PER CASE, fitted on that case's documents only,
    and persisted to its own pickle file keyed by case_id.
  - ChromaDB stores vectors + metadata on disk (persistent), partitioned
    logically by case_id in the "where" filter on every query.
  - Cosine similarity used for ranking results.

WHY PER-CASE VECTORIZERS (IMPORTANT FIX):
  TF-IDF vector dimensions and meaning depend entirely on the vocabulary
  it was fit on. If a single shared vectorizer were refit every time a
  new case is uploaded, every earlier case's stored vectors would become
  stale/meaningless the moment a second case is indexed — the vectorizer's
  vocabulary (and therefore vector dimensions) would silently shift out
  from under them, corrupting search for any case other than the most
  recently uploaded one. Keeping one vectorizer per case_id, saved as
  "tfidf_vectorizer_{case_id}.pkl", makes every case's search independent
  and correct regardless of upload order.

INTERVIEW EXPLANATION:
  "I used TF-IDF with ChromaDB because the forensic environment
  may not have internet access. TF-IDF gives high weights to rare
  forensic terms like crypto addresses, which is actually ideal.
  Each case gets its own fitted vectorizer, stored and loaded by case_id,
  so multiple cases never interfere with each other's search results.
  In production I'd upgrade to sentence-transformers, which wouldn't need
  per-case fitting at all since the embedding space is fixed and shared."
"""

import pickle
import re
import chromadb
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from typing import Optional
from backend.config import settings


class ForensicVectorStore:
    VECTORIZER_DIR = Path(settings.CHROMA_DB_DIR) / "vectorizers"

    def __init__(self):
        Path(settings.CHROMA_DB_DIR).mkdir(parents=True, exist_ok=True)
        self.VECTORIZER_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        # In-memory cache of loaded vectorizers, keyed by case_id, so we
        # don't hit disk on every single search call.
        self._vectorizer_cache: dict[str, TfidfVectorizer] = {}
        print(f"✅ Vector store ready ({self.collection.count()} docs indexed)")

    def _vectorizer_path(self, case_id: str) -> Path:
        # Sanitize case_id for safe use as a filename.
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", case_id)
        return self.VECTORIZER_DIR / f"tfidf_vectorizer_{safe_id}.pkl"

    def _load_vectorizer(self, case_id: str) -> Optional[TfidfVectorizer]:
        """Load (or fetch from cache) the vectorizer fitted for this case."""
        if case_id in self._vectorizer_cache:
            return self._vectorizer_cache[case_id]

        path = self._vectorizer_path(case_id)
        if path.exists():
            try:
                with open(path, "rb") as f:
                    vec = pickle.load(f)
                self._vectorizer_cache[case_id] = vec
                return vec
            except Exception:
                return None
        return None

    def _save_vectorizer(self, case_id: str, vectorizer: TfidfVectorizer):
        with open(self._vectorizer_path(case_id), "wb") as f:
            pickle.dump(vectorizer, f)
        self._vectorizer_cache[case_id] = vectorizer

    def _make_id(self, case_id: str, record_id: str) -> str:
        return f"{case_id}::{record_id}"

    def index_all(self, case_id: str, chats: list, calls: list, contacts: list) -> dict:
        """
        Index ALL records for a case in ONE operation.
        Fits a fresh TF-IDF vectorizer on this case's full corpus (so all
        of this case's vectors share consistent dimensions), and saves
        that vectorizer scoped to case_id so other cases are unaffected.

        Returns: dict with counts
        """
        all_documents = []
        all_metadatas = []
        all_ids = []

        # Build chat documents
        for chat in chats:
            text = (
                f"Platform {chat.platform}. "
                f"From {chat.sender} to {chat.receiver}. "
                f"Message: {chat.message_text}"
            )
            if chat.entities_json:
                kws = chat.entities_json.get("suspicious_keywords", [])
                ctypes = chat.entities_json.get("crypto_types", [])
                addrs = chat.entities_json.get("crypto_addresses", [])
                if kws or ctypes:
                    text += f". Keywords: {' '.join(kws + ctypes)}"
                if addrs:
                    text += f". Addresses: {' '.join(addrs)}"

            all_documents.append(text)
            all_ids.append(self._make_id(case_id, chat.id))
            all_metadatas.append({
                "case_id": case_id, "record_id": chat.id,
                "record_type": "chat", "platform": chat.platform or "Unknown",
                "sender": chat.sender or "", "receiver": chat.receiver or "",
                "timestamp": chat.timestamp or "",
                "risk_score": float(chat.risk_score or 0),
                "is_flagged": "true" if chat.is_flagged else "false",
            })

        # Build call documents
        for call in calls:
            text = (
                f"Phone call from {call.caller_number} to {call.receiver_number}. "
                f"Duration {call.duration_seconds} seconds. "
                f"Type {call.call_type}. Platform {call.platform}. "
                f"{'Foreign international number involved.' if call.is_foreign_number else 'Domestic call.'}"
            )
            all_documents.append(text)
            all_ids.append(self._make_id(case_id, call.id))
            all_metadatas.append({
                "case_id": case_id, "record_id": call.id,
                "record_type": "call", "caller": call.caller_number or "",
                "receiver": call.receiver_number or "",
                "platform": call.platform or "GSM",
                "call_type": call.call_type or "unknown",
                "duration_seconds": int(call.duration_seconds or 0),
                "is_foreign": "true" if call.is_foreign_number else "false",
                "risk_score": float(call.risk_score or 0),
                "timestamp": call.timestamp or "",
            })

        # Build contact documents
        for contact in contacts:
            phones = " ".join(contact.phone_numbers or [])
            emails = " ".join(contact.email_addresses or [])
            text = (
                f"Contact {contact.name}. "
                f"Phones {phones}. Email {emails}. "
                f"Organization {contact.organization}. Notes {contact.notes}."
            )
            all_documents.append(text)
            all_ids.append(self._make_id(case_id, contact.id))
            all_metadatas.append({
                "case_id": case_id, "record_id": contact.id,
                "record_type": "contact", "name": contact.name or "Unknown",
                "risk_score": float(contact.risk_score or 0),
            })

        if not all_documents:
            return {"chats": 0, "calls": 0, "contacts": 0}

        # Fit a fresh TF-IDF vectorizer on THIS CASE's documents only, and
        # save it under this case_id so re-indexing or searching this case
        # later always uses a vectorizer whose vocabulary matches what was
        # actually stored — independent of any other case's data.
        vectorizer = TfidfVectorizer(
            max_features=3000,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        vectorizer.fit(all_documents)
        self._save_vectorizer(case_id, vectorizer)

        # Compute all embeddings at once
        embeddings = vectorizer.transform(all_documents).toarray().tolist()

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(all_documents), batch_size):
            self.collection.upsert(
                embeddings=embeddings[i:i + batch_size],
                documents=all_documents[i:i + batch_size],
                metadatas=all_metadatas[i:i + batch_size],
                ids=all_ids[i:i + batch_size],
            )

        return {"chats": len(chats), "calls": len(calls), "contacts": len(contacts)}

    # Keep individual methods for backwards compatibility
    def index_chat_messages(self, case_id: str, chats: list) -> int:
        """Index only chats (use index_all() for full case indexing)."""
        return self.index_all(case_id, chats, [], [])["chats"]

    def index_call_records(self, case_id: str, calls: list) -> int:
        return self.index_all(case_id, [], calls, [])["calls"]

    def index_contacts(self, case_id: str, contacts: list) -> int:
        return self.index_all(case_id, [], [], contacts)["contacts"]

    def semantic_search(
        self,
        query: str,
        case_id: str,
        n_results: int = None,
        record_type: str = None,
        min_risk: float = None,
    ) -> list[dict]:
        """Find records most similar to query using TF-IDF cosine similarity."""
        if n_results is None:
            n_results = settings.RAG_TOP_K

        vectorizer = self._load_vectorizer(case_id)
        if vectorizer is None or self.collection.count() == 0:
            return []

        where_conditions = [{"case_id": {"$eq": case_id}}]
        if record_type:
            where_conditions.append({"record_type": {"$eq": record_type}})
        where = ({"$and": where_conditions}
                 if len(where_conditions) > 1 else where_conditions[0])

        try:
            query_vec = vectorizer.transform([query]).toarray().tolist()
            results = self.collection.query(
                query_embeddings=query_vec,
                n_results=min(n_results, self.collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            print(f"⚠️  Semantic search error: {e}")
            return []

        if not results.get("documents") or not results["documents"][0]:
            return []

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = round(max(0.0, 1 - dist), 4)
            if min_risk and float(meta.get("risk_score", 0)) < min_risk:
                continue
            output.append({
                "document": doc,
                "metadata": meta,
                "similarity_score": similarity,
                "record_type": meta.get("record_type", "unknown"),
                "record_id": meta.get("record_id", ""),
                "risk_score": float(meta.get("risk_score", 0)),
            })

        output.sort(key=lambda x: x["similarity_score"], reverse=True)
        return output

    def get_all_for_rag(self, case_id: str, record_type: str = "chat") -> list[str]:
        """Retrieve all document texts for RAG context (used in Phase 3)."""
        try:
            results = self.collection.get(
                where={"$and": [
                    {"case_id": {"$eq": case_id}},
                    {"record_type": {"$eq": record_type}},
                ]},
                include=["documents"],
            )
            return results.get("documents", [])
        except Exception:
            return []

    def delete_case_documents(self, case_id: str):
        try:
            self.collection.delete(where={"case_id": {"$eq": case_id}})
        except Exception as e:
            print(f"⚠️  ChromaDB delete: {e}")

        # Also remove this case's saved vectorizer so reindexing starts clean.
        try:
            path = self._vectorizer_path(case_id)
            if path.exists():
                path.unlink()
            self._vectorizer_cache.pop(case_id, None)
        except Exception as e:
            print(f"⚠️  Vectorizer cleanup failed: {e}")

    def get_case_stats(self, case_id: str) -> dict:
        """
        Count only THIS case's indexed documents, not the whole collection.
        (Previously this returned self.collection.count(), which is the
        total across every case ever indexed — misleading once more than
        one case exists in the same ChromaDB collection.)
        """
        try:
            results = self.collection.get(
                where={"case_id": {"$eq": case_id}},
                include=[],
            )
            return {"total_indexed": len(results.get("ids", []))}
        except Exception:
            return {"total_indexed": 0}


# ── Singleton ─────────────────────────────────────────────────
_instance: Optional[ForensicVectorStore] = None

def get_vector_store() -> ForensicVectorStore:
    global _instance
    if _instance is None:
        _instance = ForensicVectorStore()
    return _instance