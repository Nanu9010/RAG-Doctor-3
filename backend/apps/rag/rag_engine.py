"""
Doctor RAG – RAG Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Orchestrates: retrieval → strict grounded-prompt → LLM → hallucination check

The system prompt STRICTLY forbids the LLM from using parametric (training)
knowledge.  Every factual claim must be traceable to a retrieved chunk.
"""
import logging
import time
from typing import Dict, Any, Optional, List

from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from .vector_store import VectorStore
from .hallucination_guard import HallucinationGuard

logger = logging.getLogger("apps.rag")


# ─────────────────────────────────────────────────────────────────────────────
# System Prompt – Anti-Hallucination Enforced
# ─────────────────────────────────────────────────────────────────────────────

RAG_SYSTEM_PROMPT = """You are a clinical decision-support assistant for licensed medical professionals.

CRITICAL RULES – READ CAREFULLY:
1. You MUST answer ONLY using the information provided in the <context> blocks below.
2. You are STRICTLY FORBIDDEN from using your training knowledge to add facts,
   treatments, dosages, or recommendations not explicitly stated in the context.
3. If the context does not contain sufficient information to answer the question,
   you MUST respond: "The retrieved documents do not contain enough information
   to answer this question. Please consult primary clinical references."
4. Do NOT speculate, extrapolate, or infer beyond what is written in the context.
5. Always cite which source/document your information comes from using [Source: X] notation.
6. If you mention a drug, dosage, or procedure, it MUST appear verbatim in the context.
7. Structure your answer clearly: Summary → Details → Caveats → Sources.

RESPONSE FORMAT:
- Use clear medical language appropriate for a licensed doctor.
- Include section headers for multi-part answers.
- End every response with a "Sources" section listing all referenced documents.
- Never provide a differential diagnosis without explicit context support.
"""


def _build_context_block(chunks: List[Dict]) -> str:
    """Formats retrieved chunks into the prompt context block."""
    if not chunks:
        return "<context>\nNo relevant documents found.\n</context>"

    lines = ["<context>"]
    seen_sources = set()
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", "Unknown")
        date = chunk.get("date", "")
        specialty = chunk.get("speciality", "")
        doc_id = chunk.get("doc_id", "")
        score = chunk.get("score", 0.0)

        lines.append(
            f"\n[Chunk {i}] Source: {source} | Specialty: {specialty} | "
            f"Date: {date} | DocID: {doc_id} | Relevance: {score:.2f}"
        )
        lines.append(chunk["chunk_text"])
        seen_sources.add(source)

    lines.append("\n</context>")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main Engine
# ─────────────────────────────────────────────────────────────────────────────

class RAGEngine:
    """
    Full RAG pipeline:
      query → VectorStore.search → LLM(grounded) → HallucinationGuard → result
    """

    def __init__(self):
        self.vector_store = VectorStore()
        self.llm = ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL,
            temperature=0.0,    # deterministic for medical accuracy
            openai_api_key=settings.OPENAI_API_KEY,
            max_tokens=1500,
        )
        self.guard = HallucinationGuard()

    def query(
        self,
        question: str,
        specialty_filter: Optional[str] = None,
        top_k: int = None,
        doctor_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point for a RAG query.

        Returns:
        {
            "answer": str,
            "sources": [...],
            "retrieved_chunks": [...],
            "confidence_score": float,
            "confidence_label": str,
            "is_hallucination_risk": bool,
            "warning_message": str,
            "sentence_grounding": [...],
            "response_time_ms": int,
            "speciality_filter": str,
        }
        """
        start = time.time()
        top_k = top_k or settings.SIMILARITY_TOP_K

        # ── Step 1: Retrieve relevant chunks ──────────────────────────────────
        logger.info("RAG query: %s [filter=%s]", question[:80], specialty_filter)
        chunks = self.vector_store.search(
            query=question,
            top_k=top_k,
            specialty_filter=specialty_filter,
        )
        logger.debug("Retrieved %d chunks", len(chunks))

        # ── Step 2: Build context block ───────────────────────────────────────
        context_block = _build_context_block(chunks)

        # ── Step 3: Build user message ────────────────────────────────────────
        doctor_info = ""
        if doctor_context:
            doctor_info = (
                f"\nThe clinician asking this question specialises in "
                f"{doctor_context.get('specialty', 'general medicine')}."
            )

        user_message = f"""Medical Question: {question}{doctor_info}

{context_block}

Please answer based EXCLUSIVELY on the context provided above.
"""

        # ── Step 4: Call LLM ──────────────────────────────────────────────────
        messages = [
            SystemMessage(content=RAG_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        try:
            response = self.llm.invoke(messages)
            answer = response.content.strip()
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return {
                "answer": "Service temporarily unavailable. Please try again.",
                "error": str(e),
                "confidence_score": 0.0,
                "is_hallucination_risk": True,
                "sources": [],
                "retrieved_chunks": chunks,
                "response_time_ms": int((time.time() - start) * 1000),
            }

        # ── Step 5: Hallucination Check ───────────────────────────────────────
        guard_result = self.guard.evaluate(answer, chunks)

        # ── Step 6: Build source list ─────────────────────────────────────────
        sources = self._deduplicate_sources(chunks)

        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "RAG complete – confidence=%.3f, hallucination_risk=%s, time=%dms",
            guard_result["confidence_score"],
            guard_result["is_hallucination_risk"],
            elapsed_ms,
        )

        return {
            "answer": answer,
            "sources": sources,
            "retrieved_chunks": chunks,
            "confidence_score": guard_result["confidence_score"],
            "confidence_label": guard_result["confidence_label"],
            "is_hallucination_risk": guard_result["is_hallucination_risk"],
            "warning_message": guard_result["warning_message"],
            "sentence_grounding": guard_result["sentence_grounding"],
            "token_overlap_score": guard_result["token_overlap_score"],
            "semantic_score": guard_result["semantic_score"],
            "response_time_ms": elapsed_ms,
            "speciality_filter": specialty_filter or "all",
            "chunks_retrieved": len(chunks),
        }

    @staticmethod
    def _deduplicate_sources(chunks: List[Dict]) -> List[Dict]:
        """Return unique source list with highest relevance score per source."""
        seen: Dict[str, Dict] = {}
        for chunk in chunks:
            doc_id = chunk.get("doc_id", "")
            if doc_id not in seen or chunk["score"] > seen[doc_id]["score"]:
                seen[doc_id] = {
                    "doc_id": doc_id,
                    "source": chunk.get("source", ""),
                    "title": chunk.get("title", ""),
                    "speciality": chunk.get("speciality", ""),
                    "date": chunk.get("date", ""),
                    "score": chunk.get("score", 0.0),
                }
        return sorted(seen.values(), key=lambda x: x["score"], reverse=True)
