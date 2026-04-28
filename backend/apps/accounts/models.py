"""
Doctor RAG – Accounts Models
Custom Doctor user model with specialty, licence, and audit fields.
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class DoctorManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class Doctor(AbstractBaseUser, PermissionsMixin):
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
        ("general", "General Practice"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    specialty = models.CharField(
        max_length=50, choices=SPECIALTY_CHOICES, default="general"
    )
    license_number = models.CharField(max_length=50, unique=True)
    hospital = models.CharField(max_length=200, blank=True)
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    objects = DoctorManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "license_number"]

    class Meta:
        db_table = "doctors"
        ordering = ["-created_at"]
        verbose_name = "Doctor"
        verbose_name_plural = "Doctors"

    def __str__(self):
        return f"Dr. {self.first_name} {self.last_name} ({self.specialty})"

    @property
    def full_name(self):
        return f"Dr. {self.first_name} {self.last_name}"


class QueryHistory(models.Model):
    """Stores every RAG query with its answer and confidence score."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        Doctor, on_delete=models.CASCADE, related_name="query_history"
    )
    query = models.TextField()
    answer = models.TextField()
    confidence_score = models.FloatField(default=0.0)
    is_hallucination_risk = models.BooleanField(default=False)
    speciality_filter = models.CharField(max_length=50, blank=True)
    sources = models.JSONField(default=list)   # list of doc_ids + filenames
    retrieved_chunks = models.JSONField(default=list)
    response_time_ms = models.IntegerField(default=0)
    feedback = models.CharField(
        max_length=20,
        choices=[("helpful", "Helpful"), ("unhelpful", "Unhelpful"), ("pending", "Pending")],
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "query_history"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.doctor.full_name} – {self.query[:60]}"
