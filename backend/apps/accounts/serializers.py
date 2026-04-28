"""Doctor RAG – Accounts Serializers"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import Doctor, QueryHistory


class DoctorRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Doctor
        fields = [
            "email", "first_name", "last_name", "specialty",
            "license_number", "hospital", "password", "password2",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        return Doctor.objects.create_user(**validated_data)


class DoctorProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    query_count = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = [
            "id", "email", "first_name", "last_name", "full_name",
            "specialty", "license_number", "hospital", "avatar",
            "is_verified", "created_at", "query_count",
        ]
        read_only_fields = ["id", "email", "created_at", "is_verified"]

    def get_query_count(self, obj):
        return obj.query_history.count()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class QueryHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryHistory
        fields = [
            "id", "query", "answer", "confidence_score",
            "is_hallucination_risk", "speciality_filter",
            "sources", "response_time_ms", "feedback", "created_at",
        ]
        read_only_fields = fields
