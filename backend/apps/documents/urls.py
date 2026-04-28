from django.urls import path
from .views import DocumentListView, DocumentUploadView, DocumentDetailView, reindex_document

urlpatterns = [
    # GET  → list documents
    # POST → upload (frontend posts to /documents/ with multipart)
    path("",                   DocumentListView.as_view(),   name="document_list"),
    path("upload/",            DocumentUploadView.as_view(), name="document_upload"),
    path("<uuid:pk>/",         DocumentDetailView.as_view(), name="document_detail"),
    path("<uuid:pk>/reindex/", reindex_document,             name="document_reindex"),
]
