from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Server-rendered views
    path("register/", views.register_view, name="register"),
    path("verify-otp/", views.verify_otp_view, name="verify_otp"),
    path("resend-otp/", views.resend_otp_view, name="resend_otp"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("chat/", views.chatbot_view, name="chatbot"),

    # REST API endpoints for React Frontend
    path("api/register/", views.api_register, name="api_register"),
    path("api/verify-otp/", views.api_verify_otp, name="api_verify_otp"),
    path("api/login/", views.api_login, name="api_login"),
    path("api/me/", views.api_me, name="api_me"),
    path("api/logout/", views.api_logout, name="api_logout"),
]
