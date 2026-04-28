from qdrant_client import QdrantClient
from django.conf import settings

COLLECTION = getattr(settings, 'QDRANT_COLLECTION', 'doctor_rag_docs')

def get_qdrant_client():
    return QdrantClient(
        host=getattr(settings, 'QDRANT_HOST', 'localhost'),
        port=getattr(settings, 'QDRANT_PORT', 6333),
        api_key=getattr(settings, 'QDRANT_API_KEY', None)
    )
