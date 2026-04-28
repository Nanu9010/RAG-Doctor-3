"""
Doctor RAG – Celery Tasks
Async document ingestion: parse → chunk → embed → upsert to Qdrant
Kept here for Celery autodiscovery; actual logic lives in documents/services.py
"""
# Tasks are defined in apps.documents.tasks to avoid circular imports.
# This file intentionally left minimal so Celery autodiscovers from documents.
