"""
Doctor RAG – Accounts Views
Endpoints: register, login, logout, profile, history, stats, feedback
"""
import logging
from django.utils import timezone
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import Doctor, QueryHistory
from .serializers import (
    DoctorRegisterSerializer,
    DoctorProfileSerializer,
    ChangePasswordSerializer,
    QueryHistorySerializer,
)

logger = logging.getLogger("apps.accounts")


# ── Register ──────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register(request):
    serializer = DoctorRegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    doctor = serializer.save()
    refresh = RefreshToken.for_user(doctor)

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "doctor": DoctorProfileSerializer(doctor).data,
        },
        status=status.HTTP_201_CREATED,
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login(request):
    from django.contrib.auth import authenticate

    email = request.data.get("email", "").strip().lower()
    password = request.data.get("password", "")

    if not email or not password:
        return Response(
            {"error": "Email and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response(
            {"error": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Record login IP
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = x_forwarded.split(",")[0] if x_forwarded else request.META.get("REMOTE_ADDR")
    user.last_login_ip = ip
    user.save(update_fields=["last_login_ip"])

    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "doctor": DoctorProfileSerializer(user).data,
        }
    )


# ── Logout ────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    refresh_token = request.data.get("refresh")
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            pass  # already blacklisted or invalid – fine
    return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


# ── Profile ───────────────────────────────────────────────────────────────────

@api_view(["GET", "PUT", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
def profile(request):
    if request.method == "GET":
        return Response(DoctorProfileSerializer(request.user).data)

    serializer = DoctorProfileSerializer(
        request.user, data=request.data, partial=True
    )
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Change Password ───────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(
        data=request.data, context={"request": request}
    )
    if serializer.is_valid():
        serializer.save()
        return Response({"detail": "Password updated."})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Query History ─────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def history(request):
    qs = QueryHistory.objects.filter(doctor=request.user)
    specialty = request.query_params.get("specialty")
    if specialty:
        qs = qs.filter(speciality_filter=specialty)
    serializer = QueryHistorySerializer(qs[:50], many=True)
    return Response(serializer.data)


# ── Feedback on a history entry ───────────────────────────────────────────────

@api_view(["PATCH"])
@permission_classes([permissions.IsAuthenticated])
def history_feedback(request, pk):
    try:
        entry = QueryHistory.objects.get(pk=pk, doctor=request.user)
    except QueryHistory.DoesNotExist:
        return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    feedback = request.data.get("feedback")
    if feedback not in ("helpful", "unhelpful", "pending"):
        return Response({"error": "Invalid feedback value."}, status=status.HTTP_400_BAD_REQUEST)

    entry.feedback = feedback
    entry.save(update_fields=["feedback"])
    return Response({"detail": "Feedback saved."})


# ── Stats ─────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def stats(request):
    qs = QueryHistory.objects.filter(doctor=request.user)
    total = qs.count()

    from django.db.models import Avg, Count
    agg = qs.aggregate(avg_conf=Avg("confidence_score"))
    hallucination_flagged = qs.filter(is_hallucination_risk=True).count()
    helpful_responses = qs.filter(feedback="helpful").count()

    return Response(
        {
            "total_queries": total,
            "avg_confidence": round(agg["avg_conf"] or 0.0, 4),
            "hallucination_flagged": hallucination_flagged,
            "helpful_responses": helpful_responses,
            "specialty": request.user.specialty,
        }
    )
