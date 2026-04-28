"""
Doctor RAG – RAG Views
POST /api/v1/rag/query/          – main RAG query
POST /api/v1/rag/voice/query/    – voice → STT → RAG → TTS
GET  /api/v1/rag/collection/     – Qdrant stats
"""
import logging
import os
import tempfile
import time

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.conf import settings

from apps.accounts.models import QueryHistory
from .rag_engine import RAGEngine
from .vector_store import VectorStore

logger = logging.getLogger("apps.rag")

# Lazy-init – avoid cold-import penalty
_engine: RAGEngine = None


def get_engine() -> RAGEngine:
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine


# ─────────────────────────────────────────────────────────────────────────────
# Text Query
# ─────────────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rag_query(request):
    """
    Body:
    {
        "question": "What is the first-line treatment for hypertension?",
        "specialty_filter": "cardiology",   // optional
        "top_k": 5                           // optional, 1-10
    }
    """
    question = request.data.get("question", "").strip()
    if not question:
        return Response(
            {"error": "question is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    specialty_filter = request.data.get("specialty_filter") or None
    top_k = min(max(int(request.data.get("top_k", 5)), 1), 10)

    engine = get_engine()
    result = engine.query(
        question=question,
        specialty_filter=specialty_filter,
        top_k=top_k,
        doctor_context={"specialty": request.user.specialty},
    )

    # Persist to query history
    QueryHistory.objects.create(
        doctor=request.user,
        query=question,
        answer=result["answer"],
        confidence_score=result["confidence_score"],
        is_hallucination_risk=result["is_hallucination_risk"],
        speciality_filter=result["speciality_filter"],
        sources=result["sources"],
        retrieved_chunks=result["retrieved_chunks"],
        response_time_ms=result["response_time_ms"],
    )

    return Response(result)


# ─────────────────────────────────────────────────────────────────────────────
# Voice Query (Whisper STT → RAG → gTTS)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def voice_query(request):
    """
    Accepts audio file, transcribes with Whisper, runs RAG, returns:
    {
        "transcript": "...",
        "rag_result": {...},
        "audio_url": "/media/voice_responses/xyz.mp3"
    }
    """
    if not settings.VOICE_ENABLED:
        return Response(
            {"error": "Voice is disabled on this server."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return Response(
            {"error": "Audio file required."}, status=status.HTTP_400_BAD_REQUEST
        )

    # ── STT: Whisper ──────────────────────────────────────────────────────────
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(settings.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        segments, _ = model.transcribe(tmp_path)
        transcript = " ".join(seg.text for seg in segments).strip()
        os.unlink(tmp_path)

        if not transcript:
            return Response(
                {"error": "Could not transcribe audio."}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

    except Exception as e:
        logger.error("Whisper STT failed: %s", e)
        return Response({"error": f"STT failed: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── RAG Query ─────────────────────────────────────────────────────────────
    specialty_filter = request.data.get("specialty_filter") or None
    engine = get_engine()
    rag_result = engine.query(
        question=transcript,
        specialty_filter=specialty_filter,
        doctor_context={"specialty": request.user.specialty},
    )

    # ── TTS: gTTS ─────────────────────────────────────────────────────────────
    audio_url = None
    try:
        from gtts import gTTS
        import uuid

        tts_text = rag_result["answer"][:2000]   # limit TTS length
        tts = gTTS(text=tts_text, lang="en", slow=False)
        audio_dir = os.path.join(settings.MEDIA_ROOT, "voice_responses")
        os.makedirs(audio_dir, exist_ok=True)
        audio_filename = f"{uuid.uuid4()}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)
        tts.save(audio_path)
        audio_url = f"{settings.MEDIA_URL}voice_responses/{audio_filename}"

    except Exception as e:
        logger.warning("TTS failed (non-fatal): %s", e)

    # Persist
    QueryHistory.objects.create(
        doctor=request.user,
        query=f"[VOICE] {transcript}",
        answer=rag_result["answer"],
        confidence_score=rag_result["confidence_score"],
        is_hallucination_risk=rag_result["is_hallucination_risk"],
        speciality_filter=rag_result["speciality_filter"],
        sources=rag_result["sources"],
        retrieved_chunks=rag_result["retrieved_chunks"],
        response_time_ms=rag_result["response_time_ms"],
    )

    return Response(
        {
            "transcript": transcript,
            "rag_result": rag_result,
            "audio_url": audio_url,
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Qdrant Collection Stats
# ─────────────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def collection_stats(request):
    try:
        vs = VectorStore()
        return Response(vs.collection_info())
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
