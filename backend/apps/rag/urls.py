from django.urls import path
from . import views

urlpatterns = [
    path("query/", views.rag_query, name="rag_query"),
    path("voice/query/", views.voice_query, name="voice_query"),
    path("collection/stats/", views.collection_stats, name="collection_stats"),
]
