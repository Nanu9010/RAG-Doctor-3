"""
Doctor RAG – Vector Store (Qdrant)
Full CRUD interface over Qdrant with specialty-based filtering,
metadata-rich payloads, and batch upsert support.

Payload schema per chunk:
{
    "chunk_text": "...",
    "doc_id": "uuid-string",
    "speciality": "cardiology",
    "date": "2026",
    "source": "guideline.pdf",
    "title": "...",
    "chunk_index": 0,
    "total_chunks": 12,
}
"""
import logging
import uuid
from typing import List, Dict, Any, Optional

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger("apps.rag")


class VectorStore:
    """Singleton-like wrapper around Qdrant with OpenAI embeddings."""

    VECTOR_SIZE = 1536   # text-embedding-3-small dimensions

    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY or None,
        )
        self.collection = settings.QDRANT_COLLECTION
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self._ensure_collection()

    # ──────────────────────────────────────────────────────────────────────────
    # Collection Management
    # ──────────────────────────────────────────────────────────────────────────

    def _ensure_collection(self):
        """Create the collection if it doesn't already exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection not in collections:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.VECTOR_SIZE, distance=Distance.COSINE
                ),
            )
            logger.info("Created Qdrant collection: %s", self.collection)

    # ──────────────────────────────────────────────────────────────────────────
    # Ingestion
    # ──────────────────────────────────────────────────────────────────────────

    def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Embed and upsert a list of document chunks.

        Each chunk dict must have:
          chunk_text, doc_id, speciality, date, source, title, chunk_index, total_chunks
        Returns list of Qdrant point IDs (strings).
        """
        if not chunks:
            return []

        texts = [c["chunk_text"] for c in chunks]
        vectors = self.embeddings.embed_documents(texts)

        point_ids = []
        points = []
        for chunk, vector in zip(chunks, vectors):
            pid = str(uuid.uuid4())
            point_ids.append(pid)
            points.append(
                PointStruct(
                    id=pid,
                    vector=vector,
                    payload={
                        "chunk_text": chunk["chunk_text"],
                        "doc_id": chunk["doc_id"],
                        "speciality": chunk.get("speciality", "general"),
                        "date": chunk.get("date", ""),
                        "source": chunk.get("source", ""),
                        "title": chunk.get("title", ""),
                        "chunk_index": chunk.get("chunk_index", 0),
                        "total_chunks": chunk.get("total_chunks", 1),
                    },
                )
            )

        # Batch upsert in groups of 100
        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection,
                points=points[i : i + batch_size],
            )

        logger.info("Upserted %d chunks into Qdrant", len(chunks))
        return point_ids

    # ──────────────────────────────────────────────────────────────────────────
    # Retrieval
    # ──────────────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        specialty_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over the vector store.
        Returns list of dicts with chunk_text, score, and full metadata.
        """
        query_vector = self.embeddings.embed_query(query)

        qdrant_filter = None
        if specialty_filter and specialty_filter != "all":
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="speciality",
                        match=MatchValue(value=specialty_filter),
                    )
                ]
            )

        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
            score_threshold=0.30,   # ignore very low similarity
        )

        return [
            {
                "chunk_text": r.payload["chunk_text"],
                "doc_id": r.payload.get("doc_id", ""),
                "speciality": r.payload.get("speciality", ""),
                "date": r.payload.get("date", ""),
                "source": r.payload.get("source", ""),
                "title": r.payload.get("title", ""),
                "chunk_index": r.payload.get("chunk_index", 0),
                "score": round(float(r.score), 4),
                "point_id": str(r.id),
            }
            for r in results
        ]

    # ──────────────────────────────────────────────────────────────────────────
    # Deletion
    # ──────────────────────────────────────────────────────────────────────────

    def delete_document(self, doc_id: str):
        """Delete all vectors belonging to a document."""
        self.client.delete(
            collection_name=self.collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
        )
        logger.info("Deleted vectors for doc_id=%s", doc_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Stats
    # ──────────────────────────────────────────────────────────────────────────

    def collection_info(self) -> Dict[str, Any]:
        info = self.client.get_collection(self.collection)
        return {
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "status": str(info.status),
        }
