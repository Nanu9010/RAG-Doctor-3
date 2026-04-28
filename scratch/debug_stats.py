import os
import sys
import django

# Add backend to sys.path
sys.path.append(os.path.abspath('backend'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.rag.vector_store import VectorStore

print("Initializing VectorStore...")
try:
    vs = VectorStore()
    print("VectorStore initialized.")
    stats = vs.collection_info()
    print("Stats:", stats)
except Exception as e:
    import traceback
    traceback.print_exc()
