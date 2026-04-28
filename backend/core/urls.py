"""
Doctor RAG System – Main URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # Versioned API
    path("api/v1/auth/",      include("apps.accounts.urls")),
    path("api/v1/rag/",       include("apps.rag.urls")),
    path("api/v1/documents/", include("apps.documents.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
