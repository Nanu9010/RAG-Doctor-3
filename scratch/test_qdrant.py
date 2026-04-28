from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')

host = os.getenv('QDRANT_HOST', '127.0.0.1')
port = int(os.getenv('QDRANT_PORT', '6333'))

print(f"Connecting to Qdrant at {host}:{port}...")
try:
    client = QdrantClient(host=host, port=port)
    collections = client.get_collections()
    print("Success! Collections found:", [c.name for c in collections.collections])
except Exception as e:
    print(f"Error: {e}")
