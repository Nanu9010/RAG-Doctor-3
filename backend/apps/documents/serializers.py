from rest_framework import serializers
from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "title", "file_url", "file_type", "specialty", "source",
            "publication_date", "status", "page_count", "chunk_count",
            "error_message", "created_at",
        ]
        read_only_fields = [
            "id", "status", "page_count", "chunk_count",
            "error_message", "created_at", "file_type",
        ]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class DocumentUploadSerializer(serializers.Serializer):
    file             = serializers.FileField()
    title            = serializers.CharField(max_length=255, required=False, allow_blank=True)
    specialty        = serializers.CharField(max_length=100, required=False, default="general")
    source           = serializers.CharField(max_length=255, required=False, allow_blank=True)
    publication_date = serializers.CharField(max_length=20,  required=False, allow_blank=True)

    def validate_file(self, value):
        name = value.name.lower()
        if name.endswith(".pdf"):
            return value
        if name.endswith(".docx"):
            return value
        if name.endswith(".txt"):
            return value
        raise serializers.ValidationError("Only PDF, DOCX, and TXT files are supported.")
