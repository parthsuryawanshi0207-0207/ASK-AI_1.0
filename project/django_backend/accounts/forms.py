from django import forms
from django.contrib.auth import authenticate
from captcha.fields import CaptchaField

from .models import User


class RegistrationForm(forms.ModelForm):
    """
    Signup form. CaptchaField renders an image + text input
    (django-simple-captcha) and validates the human-entered text
    against the generated image server-side -- no external service
    or API key needed.
    """

    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)
    captcha = CaptchaField(label="Enter the text shown above")

    class Meta:
        model = User
        fields = ["email"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        user = User.objects.filter(email=email).first()
        if user and user.is_verified:
            raise forms.ValidationError("An account with this email already exists and is verified. Please log in.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        # is_active stays True so the user row exists, but is_verified
        # stays False (model default) until OTP confirmation -- see
        # views.verify_otp and the login-time check in LoginForm.
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class OTPVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        label="Verification code",
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric"}),
    )


class LoginForm(forms.Form):
    """
    Validates credentials AND account state (active + verified) in one
    place, so views.login_view stays a thin wrapper rather than
    duplicating these checks.
    """

    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    captcha = CaptchaField(label="Enter the text shown above")

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            user = authenticate(self.request, email=email, password=password)
            if user is None:
                raise forms.ValidationError("Invalid email or password.")
            if not user.is_verified:
                self.unverified_user = user
                raise forms.ValidationError(
                    "This account hasn't been verified yet. We have sent a verification code to your email."
                )
            if not user.is_active:
                raise forms.ValidationError("This account has been deactivated.")
            self.user_cache = user

        return cleaned_data

    def get_user(self):
        return self.user_cache
