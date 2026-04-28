"""Celery tasks for async document ingestion."""
import logging
from celery import shared_task
from .models import Document
from .services import ingest_document

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def ingest_document_task(self, doc_id: str):
    """
    Async task: ingest a Document into Qdrant.
    Updates Document.status throughout.
    """
    try:
        doc = Document.objects.get(pk=doc_id)
    except Document.DoesNotExist:
        logger.error("[ingest_document_task] Document %s not found.", doc_id)
        return

    doc.status = "processing"
    doc.save(update_fields=["status"])

    try:
        chunk_count, page_count, point_ids = ingest_document(doc)

        doc.status      = "indexed"
        doc.chunk_count = chunk_count
        doc.page_count  = page_count
        doc.qdrant_ids  = point_ids
        doc.error_message = ""
        doc.save(update_fields=["status", "chunk_count", "page_count", "qdrant_ids", "error_message"])

    except Exception as exc:
        logger.error("[ingest_document_task] doc_id=%s failed: %s", doc_id, exc)
        try:
            doc.status = "failed"
            doc.error_message = str(exc)[:500]
            doc.save(update_fields=["status", "error_message"])
        except Exception:
            pass
        raise self.retry(exc=exc)
