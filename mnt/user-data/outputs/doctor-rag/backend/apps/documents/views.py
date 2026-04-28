"""
Doctor RAG – Documents Views
Upload, list, delete, and trigger Qdrant ingestion for medical documents.
"""
import logging
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import serializers as drf_serializers
from django.shortcuts import get_object_or_404

from .models import MedicalDocument
from apps.rag.tasks import ingest_document_task  # Celery task

logger = logging.getLogger("apps.documents")


class MedicalDocumentSerializer(drf_serializers.ModelSerializer):
    uploaded_by_name = drf_serializers.SerializerMethodField()

    class Meta:
        model = MedicalDocument
        fields = [
            "id", "title", "file", "file_type", "specialty", "source",
            "publication_date", "uploaded_by_name", "status",
            "chunk_count", "error_message", "created_at",
        ]
        read_only_fields = ["id", "status", "chunk_count", "error_message", "created_at"]

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.full_name if obj.uploaded_by else "Unknown"


class DocumentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MedicalDocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = MedicalDocument.objects.all()
        specialty = self.request.query_params.get("specialty")
        if specialty:
            qs = qs.filter(specialty=specialty)
        return qs

    def create(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "File required."}, status=status.HTTP_400_BAD_REQUEST)

        # Detect file type
        name = file.name.lower()
        if name.endswith(".pdf"):
            file_type = "pdf"
        elif name.endswith(".docx"):
            file_type = "docx"
        elif name.endswith(".txt"):
            file_type = "txt"
        else:
            return Response(
                {"error": "Only PDF, DOCX, TXT files are supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc = MedicalDocument.objects.create(
            title=request.data.get("title", file.name),
            file=file,
            file_type=file_type,
            specialty=request.data.get("specialty", "general"),
            source=request.data.get("source", ""),
            publication_date=request.data.get("publication_date", ""),
            uploaded_by=request.user,
            status="pending",
        )

        # Kick off async ingestion
        ingest_document_task.delay(str(doc.id))
        logger.info("Document queued for ingestion: %s (%s)", doc.title, doc.id)

        return Response(
            MedicalDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MedicalDocumentSerializer
    queryset = MedicalDocument.objects.all()

    def destroy(self, request, *args, **kwargs):
        doc = self.get_object()
        # Remove vectors from Qdrant
        from apps.rag.vector_store import VectorStore
        try:
            vs = VectorStore()
            vs.delete_document(str(doc.id))
            logger.info("Deleted vectors for doc %s", doc.id)
        except Exception as e:
            logger.error("Failed to delete vectors: %s", e)

        doc.file.delete(save=False)
        doc.delete()
        return Response({"message": "Document deleted."}, status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reindex_document(request, pk):
    """Re-trigger Qdrant ingestion for an existing document."""
    doc = get_object_or_404(MedicalDocument, pk=pk)
    doc.status = "pending"
    doc.error_message = ""
    doc.save(update_fields=["status", "error_message"])
    ingest_document_task.delay(str(doc.id))
    return Response({"message": "Re-indexing started."})
