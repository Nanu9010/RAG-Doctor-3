import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id",               models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("title",            models.CharField(max_length=255)),
                ("file",             models.FileField(upload_to="docs/")),
                ("file_type",        models.CharField(max_length=10, choices=[("pdf","PDF"),("docx","DOCX"),("txt","TXT")], default="pdf")),
                ("specialty",        models.CharField(max_length=100, default="general")),
                ("source",           models.CharField(max_length=255, blank=True)),
                ("publication_date", models.CharField(max_length=20, blank=True)),
                ("status",           models.CharField(max_length=20, choices=[("pending","Pending"),("processing","Processing"),("indexed","Indexed"),("failed","Failed")], default="pending")),
                ("page_count",       models.IntegerField(default=0)),
                ("chunk_count",      models.IntegerField(default=0)),
                ("qdrant_ids",       models.JSONField(default=list)),
                ("error_message",    models.TextField(blank=True)),
                ("created_at",       models.DateTimeField(auto_now_add=True)),
                ("updated_at",       models.DateTimeField(auto_now=True)),
                ("user",             models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
