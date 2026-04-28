import uuid
from django.db import models
from django.conf import settings


def _upload_path(instance, filename):
    return f"docs/{instance.user_id}/{filename}"


class Document(models.Model):
    STATUS_CHOICES = [
        ("pending",    "Pending"),
        ("processing", "Processing"),
        ("indexed",    "Indexed"),
        ("failed",     "Failed"),
    ]
    FILE_TYPE_CHOICES = [
        ("pdf",  "PDF"),
        ("docx", "DOCX"),
        ("txt",  "TXT"),
    ]

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    title            = models.CharField(max_length=255)
    file             = models.FileField(upload_to=_upload_path)
    file_type        = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default="pdf")
    specialty        = models.CharField(max_length=100, default="general")
    source           = models.CharField(max_length=255, blank=True, help_text="Journal / publisher name")
    publication_date = models.CharField(max_length=20, blank=True, help_text="e.g. 2023")
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    page_count       = models.IntegerField(default=0)
    chunk_count      = models.IntegerField(default=0)
    qdrant_ids       = models.JSONField(default=list)
    error_message    = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def filename(self):
        return self.file.name.split("/")[-1] if self.file else ""
