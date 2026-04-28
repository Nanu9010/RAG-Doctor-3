"""Doctor RAG – Documents URL Routes"""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.DocumentListCreateView.as_view(), name="document_list_create"),
    path("<uuid:pk>/", views.DocumentDetailView.as_view(), name="document_detail"),
    path("<uuid:pk>/reindex/", views.reindex_document, name="reindex_document"),
]
