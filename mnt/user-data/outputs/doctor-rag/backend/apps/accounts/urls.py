"""Doctor RAG – Accounts URL Routes"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("history/", views.QueryHistoryView.as_view(), name="query_history"),
    path("history/<uuid:pk>/feedback/", views.feedback_view, name="feedback"),
    path("stats/", views.stats_view, name="stats"),
]
