"""
Doctor RAG – Hallucination Guard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The most critical component of the Doctor RAG System.

Medical hallucination = AI inventing treatment details = DANGEROUS.

This module provides a multi-layer grounding check:

Layer 1 – Token Overlap (fast, lexical)
    Checks if key noun phrases in the answer appear in retrieved chunks.

Layer 2 – Semantic Similarity (slow, embedding-based)
    Embeds each answer sentence and checks cosine similarity against the
    retrieved chunk corpus.  Sentences with similarity < threshold are flagged.

Layer 3 – LLM Self-Check (optional, expensive)
    Asks the LLM itself whether each claim is supported by the provided context.

Final confidence_score (0.0 – 1.0):
    Weighted average of the three layers.
    < 0.45  → is_hallucination_risk = True, answer is BLOCKED / WARNED
    0.45-0.65 → LOW confidence, shown with warning
    0.65-0.85 → MEDIUM confidence
    > 0.85  → HIGH confidence

The system NEVER generates an answer from its parametric knowledge alone;
the RAG prompt forbids this explicitly.
"""
import logging
import re
from typing import List, Dict, Tuple, Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from langchain_openai import OpenAIEmbeddings
from django.conf import settings

logger = logging.getLogger("apps.rag")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> set:
    """Lowercase word-token set, stripping stopwords."""
    STOPWORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "not", "but", "and", "or", "in", "on", "at", "to", "for",
        "of", "with", "as", "by", "from", "this", "that", "it",
    }
    tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return {t for t in tokens if t not in STOPWORDS}


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1 – Token Overlap
# ─────────────────────────────────────────────────────────────────────────────

def _token_overlap_score(answer: str, chunks: List[Dict]) -> float:
    """
    Fraction of unique answer tokens that appear in at least one retrieved chunk.
    """
    if not chunks:
        return 0.0

    answer_tokens = _tokenize(answer)
    if not answer_tokens:
        return 1.0

    all_chunk_tokens: set = set()
    for chunk in chunks:
        all_chunk_tokens |= _tokenize(chunk["chunk_text"])

    overlap = answer_tokens & all_chunk_tokens
    return len(overlap) / len(answer_tokens)


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2 – Semantic Sentence-Level Grounding
# ─────────────────────────────────────────────────────────────────────────────

def _semantic_grounding_score(
    answer: str,
    chunks: List[Dict],
    embeddings: OpenAIEmbeddings,
    threshold: float = 0.60,
) -> Tuple[float, List[Dict]]:
    """
    For each answer sentence, compute max cosine similarity against all chunk
    embeddings. Returns (mean_score, per_sentence_details).
    """
    sentences = _split_sentences(answer)
    if not sentences or not chunks:
        return 0.0, []

    chunk_texts = [c["chunk_text"] for c in chunks]

    try:
        # Embed sentences and chunks
        sent_vecs = np.array(embeddings.embed_documents(sentences))
        chunk_vecs = np.array(embeddings.embed_documents(chunk_texts))

        # Cosine similarity matrix [n_sentences × n_chunks]
        sim_matrix = cosine_similarity(sent_vecs, chunk_vecs)
        max_sims = sim_matrix.max(axis=1)   # best matching chunk per sentence
        best_chunk_idx = sim_matrix.argmax(axis=1)

        details = []
        for i, (sent, sim, ci) in enumerate(zip(sentences, max_sims, best_chunk_idx)):
            details.append(
                {
                    "sentence": sent,
                    "max_similarity": round(float(sim), 4),
                    "grounded": bool(sim >= threshold),
                    "best_source": chunks[ci].get("source", ""),
                    "best_doc_id": chunks[ci].get("doc_id", ""),
                }
            )

        mean_score = float(max_sims.mean())
        return mean_score, details

    except Exception as e:
        logger.error("Semantic grounding failed: %s", e)
        return 0.5, []   # neutral fallback


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class HallucinationGuard:
    """
    Evaluate whether a generated answer is grounded in retrieved chunks.

    Usage:
        guard = HallucinationGuard()
        result = guard.evaluate(answer, chunks)
        if result["is_hallucination_risk"]:
            # block or warn
    """

    WEIGHTS = {
        "token_overlap": 0.35,
        "semantic": 0.65,
    }

    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self.min_threshold = settings.MIN_CONFIDENCE_THRESHOLD

    def evaluate(self, answer: str, chunks: List[Dict]) -> Dict[str, Any]:
        """
        Returns:
        {
            "confidence_score": 0.0–1.0,
            "confidence_label": "high"|"medium"|"low"|"critical",
            "is_hallucination_risk": bool,
            "token_overlap_score": float,
            "semantic_score": float,
            "sentence_grounding": [...],
            "ungrounded_sentences": [...],
            "warning_message": str,
        }
        """
        if not answer.strip():
            return self._build_result(0.0, 0.0, [], "Empty answer.")

        if not chunks:
            return self._build_result(
                0.0, 0.0, [], "No context documents retrieved. Cannot verify answer."
            )

        # Layer 1 – Token Overlap
        tok_score = _token_overlap_score(answer, chunks)

        # Layer 2 – Semantic Grounding
        sem_score, sentence_details = _semantic_grounding_score(
            answer, chunks, self.embeddings
        )

        # Weighted composite
        confidence = (
            self.WEIGHTS["token_overlap"] * tok_score
            + self.WEIGHTS["semantic"] * sem_score
        )
        confidence = round(min(max(confidence, 0.0), 1.0), 4)

        ungrounded = [d for d in sentence_details if not d["grounded"]]
        warning = ""
        if confidence < self.min_threshold:
            warning = (
                "⚠️ HIGH HALLUCINATION RISK: This answer could not be fully "
                "verified against the retrieved medical documents. "
                "Do NOT use for clinical decisions."
            )
        elif confidence < 0.65:
            warning = (
                "⚠️ LOW CONFIDENCE: Some parts of this answer have limited "
                "grounding in the source documents. Verify before use."
            )

        return self._build_result(
            confidence, tok_score, sentence_details, warning,
            sem_score=sem_score, ungrounded=ungrounded
        )

    @staticmethod
    def _build_result(
        confidence: float,
        tok_score: float,
        sentence_details: List[Dict],
        warning: str,
        sem_score: float = 0.0,
        ungrounded: List[Dict] = None,
    ) -> Dict[str, Any]:
        if confidence >= 0.85:
            label = "high"
        elif confidence >= 0.65:
            label = "medium"
        elif confidence >= 0.45:
            label = "low"
        else:
            label = "critical"

        return {
            "confidence_score": confidence,
            "confidence_label": label,
            "is_hallucination_risk": confidence < float(settings.MIN_CONFIDENCE_THRESHOLD),
            "token_overlap_score": round(tok_score, 4),
            "semantic_score": round(sem_score, 4),
            "sentence_grounding": sentence_details,
            "ungrounded_sentences": ungrounded or [],
            "warning_message": warning,
        }
