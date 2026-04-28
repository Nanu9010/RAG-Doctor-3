from langchain_openai import OpenAIEmbeddings
from django.conf import settings

def get_embedder():
    return OpenAIEmbeddings(
        openai_api_key=getattr(settings, 'OPENAI_API_KEY', ''),
        model=getattr(settings, 'OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
    )
