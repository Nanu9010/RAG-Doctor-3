"""
Doctor RAG – Document Views
GET/POST  /api/v1/documents/          – list / upload
GET/DELETE /api/v1/documents/<id>/    – detail / delete
POST       /api/v1/documents/<id>/reindex/ – re-trigger ingestion
"""
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Document
from .serializers import DocumentSerializer, DocumentUploadSerializer
from .tasks import ingest_document_task


def _create_doc_from_upload(request, serializer):
    """Shared helper: create Document + dispatch Celery task."""
    f = serializer.validated_data["file"]
    name = f.name.lower()
    if name.endswith(".pdf"):
        ftype = "pdf"
    elif name.endswith(".docx"):
        ftype = "docx"
    else:
        ftype = "txt"

    doc = Document.objects.create(
        user=request.user,
        file=f,
        title=serializer.validated_data.get("title") or f.name.rsplit(".", 1)[0],
        file_type=ftype,
        specialty=serializer.validated_data.get("specialty", "general"),
        source=serializer.validated_data.get("source", ""),
        publication_date=serializer.validated_data.get("publication_date", ""),
    )
    ingest_document_task.delay(str(doc.id))
    return doc


class DocumentListView(generics.ListCreateAPIView):
    """
    GET  → list user's documents
    POST → upload a new document (multipart/form-data)
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return DocumentUploadSerializer
        return DocumentSerializer

    def get_queryset(self):
        return Document.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = _create_doc_from_upload(request, serializer)
        return Response(
            DocumentSerializer(doc, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentUploadView(generics.CreateAPIView):
    """POST /api/v1/documents/upload/ — alternate upload endpoint."""
    serializer_class = DocumentUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = _create_doc_from_upload(request, serializer)
        return Response(
            DocumentSerializer(doc, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        if instance.qdrant_ids:
            try:
                from apps.rag.vector_store import VectorStore
                VectorStore().delete_document(str(instance.id))
            except Exception:
                pass
        instance.file.delete(save=False)
        instance.delete()


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def reindex_document(request, pk):
    try:
        doc = Document.objects.get(pk=pk, user=request.user)
    except Document.DoesNotExist:
        return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    doc.status = "pending"
    doc.error_message = ""
    doc.save(update_fields=["status", "error_message"])
    ingest_document_task.delay(str(doc.id))
    return Response({"detail": "Re-indexing started."})
