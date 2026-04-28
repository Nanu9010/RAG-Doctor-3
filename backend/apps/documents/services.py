"""
Document ingestion service: extract text → chunk → embed → upsert into Qdrant.
"""
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


def _extract_text(path: str, file_type: str) -> tuple:
    """Return (text, page_count)."""
    if file_type == "pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        text = "".join(page.get_text() for page in doc)
        return text, len(doc)

    if file_type == "docx":
        from docx import Document as DocxDocument
        doc = DocxDocument(path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return text, 1

    # txt
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return text, 1


def _chunk_text(text: str):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def ingest_document(doc) -> tuple:
    """
    Full ingestion pipeline for a Document instance.
    Returns: (chunk_count, page_count, point_ids)
    """
    from apps.rag.vector_store import VectorStore

    path = doc.file.path
    text, page_count = _extract_text(path, doc.file_type)

    if not text.strip():
        raise ValueError(
            "Document appears empty or unreadable (possibly a scanned PDF — OCR not enabled)."
        )

    raw_chunks = _chunk_text(text)
    total = len(raw_chunks)

    chunk_dicts = [
        {
            "chunk_text": chunk,
            "doc_id": str(doc.id),
            "speciality": doc.specialty,
            "date": doc.publication_date or "",
            "source": doc.source or doc.filename,
            "title": doc.title,
            "chunk_index": i,
            "total_chunks": total,
        }
        for i, chunk in enumerate(raw_chunks)
    ]

    vs = VectorStore()
    point_ids = vs.upsert_chunks(chunk_dicts)

    logger.info("[ingest_document] %s | pages=%d | chunks=%d", doc.title, page_count, total)
    return total, page_count, point_ids
