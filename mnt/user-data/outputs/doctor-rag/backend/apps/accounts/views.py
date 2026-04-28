"""
Doctor RAG – Accounts Views
JWT authentication: register, login, refresh, logout, profile, history
"""
import logging
from django.contrib.auth import authenticate
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
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


def _get_tokens(user):
    """Return access + refresh JWT pair."""
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DoctorRegisterSerializer(data=request.data)
        if serializer.is_valid():
            doctor = serializer.save()
            tokens = _get_tokens(doctor)
            logger.info("New doctor registered: %s", doctor.email)
            return Response(
                {
                    "message": "Registration successful.",
                    "doctor": DoctorProfileSerializer(doctor).data,
                    **tokens,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, email=email, password=password)
        if not user:
            logger.warning("Failed login attempt for %s", email)
            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "Account is deactivated."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Store login IP
        ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR"))
        user.last_login_ip = ip
        user.save(update_fields=["last_login_ip"])

        tokens = _get_tokens(user)
        logger.info("Doctor logged in: %s from %s", email, ip)
        return Response(
            {
                "message": "Login successful.",
                "doctor": DoctorProfileSerializer(user).data,
                **tokens,
            }
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info("Doctor logged out: %s", request.user.email)
            return Response({"message": "Logged out successfully."})
        except TokenError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DoctorProfileSerializer

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password updated successfully."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QueryHistoryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = QueryHistorySerializer

    def get_queryset(self):
        qs = self.request.user.query_history.all()
        specialty = self.request.query_params.get("specialty")
        if specialty:
            qs = qs.filter(speciality_filter=specialty)
        return qs


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def feedback_view(request, pk):
    """Mark a query as helpful / unhelpful."""
    try:
        qh = QueryHistory.objects.get(pk=pk, doctor=request.user)
    except QueryHistory.DoesNotExist:
        return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    feedback = request.data.get("feedback")
    if feedback not in ("helpful", "unhelpful"):
        return Response({"error": "Invalid feedback value."}, status=status.HTTP_400_BAD_REQUEST)

    qh.feedback = feedback
    qh.save(update_fields=["feedback"])
    return Response({"message": "Feedback recorded."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stats_view(request):
    """Dashboard statistics for the logged-in doctor."""
    qs = request.user.query_history.all()
    total = qs.count()
    hallucination_count = qs.filter(is_hallucination_risk=True).count()
    helpful_count = qs.filter(feedback="helpful").count()
    avg_confidence = (
        qs.aggregate(avg=__import__("django.db.models", fromlist=["Avg"]).Avg("confidence_score"))["avg"]
        or 0.0
    )

    return Response(
        {
            "total_queries": total,
            "hallucination_flagged": hallucination_count,
            "helpful_responses": helpful_count,
            "avg_confidence": round(avg_confidence, 2),
            "specialty": request.user.specialty,
        }
    )
