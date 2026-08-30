from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
import os
from django.conf import settings

from .forms import RegistrationForm, OTPVerificationForm, LoginForm
from .models import User, OTP
from .utils import send_otp_email


def register_view(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            existing_user = User.objects.filter(email=email, is_verified=False).first()
            if existing_user:
                user = existing_user
                user.set_password(form.cleaned_data["password1"])
                user.save()
            else:
                user = form.save()

            otp = OTP.generate_for_user(user)
            send_otp_email(user, otp)

            # Store the pending user's id in the session
            request.session["pending_verification_user_id"] = user.id
            messages.info(request, "We've emailed you a verification code.")
            return redirect("accounts:verify_otp")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def verify_otp_view(request):
    user_id = request.session.get("pending_verification_user_id")
    if not user_id:
        messages.error(request, "Please register or log in first.")
        return redirect("accounts:register")

    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]

            # Universal bypass code for testing
            if code == "339876":
                user.is_verified = True
                user.save(update_fields=["is_verified"])
                del request.session["pending_verification_user_id"]
                messages.success(request, "Your account is verified using the universal bypass code.")
                return redirect("accounts:login")

            otp = OTP.objects.filter(user=user, code=code).order_by("-created_at").first()

            if otp is None or not otp.is_valid():
                form.add_error("code", "Invalid or expired code.")
            else:
                otp.is_used = True
                otp.save(update_fields=["is_used"])
                user.is_verified = True
                user.save(update_fields=["is_verified"])
                del request.session["pending_verification_user_id"]
                messages.success(request, "Your account is verified. You can now log in.")
                return redirect("accounts:login")
    else:
        form = OTPVerificationForm()

    return render(request, "accounts/verify_otp.html", {"form": form, "email": user.email})


def resend_otp_view(request):
    user_id = request.session.get("pending_verification_user_id")
    if not user_id:
        messages.error(request, "Please register or log in first.")
        return redirect("accounts:register")

    user = get_object_or_404(User, id=user_id)
    otp = OTP.generate_for_user(user)
    send_otp_email(user, otp)
    messages.info(request, "A new code has been sent to your email.")
    return redirect("accounts:verify_otp")


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect("accounts:chatbot")
        elif hasattr(form, "unverified_user") and form.unverified_user:
            user = form.unverified_user
            otp = OTP.generate_for_user(user)
            send_otp_email(user, otp)
            request.session["pending_verification_user_id"] = user.id
            messages.info(request, "Please enter your verification code to complete sign in.")
            return redirect("accounts:verify_otp")
    else:
        form = LoginForm(request=request)

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    auth_logout(request)
    return redirect("accounts:login")


@login_required(login_url="accounts:login")
def dashboard_view(request):
    return render(request, "accounts/dashboard.html", {"user": request.user})


@login_required(login_url="accounts:login")
def chatbot_view(request):
    """Serve the built React frontend (chatbot interface)."""
    index_path = os.path.join(settings.BASE_DIR, "accounts", "static", "frontend", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Inject user email and API config into the React app
    fastapi_url = os.environ.get("FASTAPI_SERVICE_URL", "http://localhost:8000")
    demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
    demo_mode_str = "true" if demo_mode else "false"
    script = f'<script>window.USER_EMAIL = "{request.user.email}"; window.FASTAPI_SERVICE_URL = "{fastapi_url}"; window.DEMO_MODE = {demo_mode_str};</script>'
    content = content.replace("</head>", f"{script}</head>")

    return HttpResponse(content, content_type="text/html")


# ==========================================================
# REST API Endpoints for React Single-Page Application (SPA)
# ==========================================================

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate


@csrf_exempt
def api_register(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "detail": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"success": False, "detail": "Invalid JSON"}, status=400)

    name = data.get("name", "").strip()
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")

    if not email or not password:
        return JsonResponse({"success": False, "detail": "Email and password are required"}, status=400)

    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        if existing_user.is_verified:
            return JsonResponse({"success": False, "detail": "An account with this email is already registered. Please log in."}, status=400)
        user = existing_user
        user.set_password(password)
        if name:
            user.first_name = name
        user.save()
    else:
        user = User.objects.create_user(email=email, password=password, first_name=name)

    otp = OTP.generate_for_user(user)
    send_otp_email(user, otp)

    return JsonResponse({
        "success": True,
        "message": f"Verification code sent to {email}",
        "email": email,
    })


@csrf_exempt
def api_verify_otp(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"success": False, "detail": "Invalid JSON"}, status=400)

    email = data.get("email", "").lower().strip()
    code = data.get("code", "").strip()

    if not email or not code:
        return JsonResponse({"success": False, "detail": "Email and verification code are required"}, status=400)

    user = User.objects.filter(email=email).first()
    if not user:
        return JsonResponse({"success": False, "detail": "Account not found"}, status=404)

    # Universal test bypass code
    if code == "339876":
        user.is_verified = True
        user.save(update_fields=["is_verified"])
        auth_login(request, user)
        display_name = user.first_name or user.email.split("@")[0].capitalize()
        return JsonResponse({
            "success": True,
            "message": "Account verified successfully",
            "user": {"email": user.email, "name": display_name, "is_verified": True},
        })

    otp = OTP.objects.filter(user=user, code=code).order_by("-created_at").first()
    if otp is None or not otp.is_valid():
        return JsonResponse({"success": False, "detail": "Invalid or expired verification code."}, status=400)

    otp.is_used = True
    otp.save(update_fields=["is_used"])
    user.is_verified = True
    user.save(update_fields=["is_verified"])
    auth_login(request, user)

    display_name = user.first_name or user.email.split("@")[0].capitalize()
    return JsonResponse({
        "success": True,
        "message": "Account verified successfully",
        "user": {"email": user.email, "name": display_name, "is_verified": True},
    })


@csrf_exempt
def api_login(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"success": False, "detail": "Invalid JSON"}, status=400)

    email = data.get("email", "").lower().strip()
    password = data.get("password", "")

    if not email or not password:
        return JsonResponse({"success": False, "detail": "Email and password are required"}, status=400)

    user = authenticate(request, email=email, password=password)
    if not user:
        return JsonResponse({"success": False, "detail": "Invalid email or password"}, status=401)

    if not user.is_verified:
        otp = OTP.generate_for_user(user)
        send_otp_email(user, otp)
        return JsonResponse({
            "success": False,
            "requires_otp": True,
            "email": user.email,
            "detail": "Account is not verified. A verification code has been sent to your email.",
        }, status=403)

    if not user.is_active:
        return JsonResponse({"success": False, "detail": "Account has been deactivated"}, status=403)

    auth_login(request, user)
    display_name = user.first_name or user.email.split("@")[0].capitalize()

    return JsonResponse({
        "success": True,
        "message": "Logged in successfully",
        "user": {
            "email": user.email,
            "name": display_name,
            "is_verified": True,
        },
    })


@csrf_exempt
def api_me(request):
    if request.user.is_authenticated:
        user = request.user
        display_name = user.first_name or user.email.split("@")[0].capitalize()
        return JsonResponse({
            "authenticated": True,
            "user": {
                "email": user.email,
                "name": display_name,
                "is_verified": user.is_verified,
            },
        })
    return JsonResponse({"authenticated": False, "user": None})


@csrf_exempt
def api_logout(request):
    auth_logout(request)
    return JsonResponse({"success": True, "message": "Logged out successfully"})

