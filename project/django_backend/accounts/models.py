import random
from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class UserManager(BaseUserManager):
    """
    Custom manager for the email-based User model.
    Email is the unique identifier instead of username.
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model. Username is dropped in favor of email as the
    unique login identifier. `is_verified` gates login until the
    account's OTP has been confirmed, so an unverified signup can never
    reach an authenticated session even if they know the password.
    """

    username = None
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(
        default=False,
        help_text="Set True only after the user confirms their email OTP.",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class OTP(models.Model):
    """
    One-time password tied to a user, used for email verification
    (and can be reused for password-reset flows later).

    Design notes:
    - Only the most recent OTP for a user is considered valid; requesting
      a new OTP (e.g. via "resend") should invalidate earlier ones rather
      than letting multiple valid codes exist at once.
    - `expires_at` is checked explicitly rather than relying on OTP length
      alone, so a leaked-but-expired code can never be replayed.
    - `is_used` prevents a valid, unexpired OTP from being replayed twice.
    """

    OTP_LENGTH = 6
    OTP_VALIDITY_MINUTES = 10

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="otps"
    )
    code = models.CharField(max_length=OTP_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP({self.user.email}, used={self.is_used})"

    @classmethod
    def generate_for_user(cls, user):
        """
        Creates a fresh OTP for the user and invalidates any earlier
        unused OTPs, so only the most recently issued code can ever work.
        """
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        code = "".join(random.choices("0123456789", k=cls.OTP_LENGTH))
        expires_at = timezone.now() + timedelta(minutes=cls.OTP_VALIDITY_MINUTES)
        return cls.objects.create(user=user, code=code, expires_at=expires_at)

    def is_valid(self):
        return (not self.is_used) and timezone.now() <= self.expires_at
