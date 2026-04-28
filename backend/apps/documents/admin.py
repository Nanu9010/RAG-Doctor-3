from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display  = ["title", "user", "specialty", "file_type", "status", "chunk_count", "page_count", "created_at"]
    list_filter   = ["status", "specialty", "file_type"]
    search_fields = ["title", "user__email"]
