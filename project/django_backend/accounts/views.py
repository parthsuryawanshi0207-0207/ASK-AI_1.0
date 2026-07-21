from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.templatetags.static import static
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
            user = form.save()
            otp = OTP.generate_for_user(user)
            send_otp_email(user, otp)

            # Store the pending user's id in the session (not the request
            # body/URL) so the verify step can't be pointed at an arbitrary
            # user id by simply editing a query string.
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
    index_path = os.path.join(settings.BASE_DIR, 'accounts', 'static', 'frontend', 'index.html')
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Inject user email into the React app
    script = f'<script>window.USER_EMAIL = "{request.user.email}";</script>'
    content = content.replace('</head>', f'{script}</head>')
    
    return HttpResponse(content, content_type='text/html')
