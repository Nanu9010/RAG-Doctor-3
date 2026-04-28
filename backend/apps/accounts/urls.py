from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path("register/",                   views.register,         name="auth_register"),
    path("login/",                      views.login,            name="auth_login"),
    path("logout/",                     views.logout,           name="auth_logout"),
    path("token/refresh/",              TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/",                    views.profile,          name="auth_profile"),
    path("change-password/",            views.change_password,  name="auth_change_password"),
    path("history/",                    views.history,          name="auth_history"),
    path("history/<uuid:pk>/feedback/", views.history_feedback, name="auth_history_feedback"),
    path("stats/",                      views.stats,            name="auth_stats"),
]
