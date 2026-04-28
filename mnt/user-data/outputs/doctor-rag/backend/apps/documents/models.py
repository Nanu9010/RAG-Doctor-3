"""
Doctor RAG – Documents Models
Tracks every medical PDF/DOCX ingested into the vector store.
"""
import uuid
from django.db import models
from apps.accounts.models import Doctor


class MedicalDocument(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("indexed", "Indexed"),
        ("failed", "Failed"),
    ]

    SPECIALTY_CHOICES = [
        ("cardiology", "Cardiology"),
        ("neurology", "Neurology"),
        ("oncology", "Oncology"),
        ("pediatrics", "Pediatrics"),
        ("radiology", "Radiology"),
        ("surgery", "Surgery"),
        ("internal_medicine", "Internal Medicine"),
        ("emergency", "Emergency Medicine"),
        ("psychiatry", "Psychiatry"),
        ("dermatology", "Dermatology"),
        ("orthopedics", "Orthopedics"),
        ("gynecology", "Gynecology"),
        ("urology", "Urology"),
        ("general", "General"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    file = models.FileField(upload_to="documents/")
    file_type = models.CharField(max_length=10)   # pdf | docx | txt
    specialty = models.CharField(max_length=50, choices=SPECIALTY_CHOICES, default="general")
    source = models.CharField(max_length=300, blank=True)   # e.g. "WHO Guideline 2026"
    publication_date = models.CharField(max_length=20, blank=True)   # e.g. "2026"
    uploaded_by = models.ForeignKey(
        Doctor, on_delete=models.SET_NULL, null=True, related_name="documents"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    chunk_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    qdrant_ids = models.JSONField(default=list)   # list of vector IDs in Qdrant
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "medical_documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} [{self.specialty}]"

    @property
    def filename(self):
        return self.file.name.split("/")[-1] if self.file else ""
