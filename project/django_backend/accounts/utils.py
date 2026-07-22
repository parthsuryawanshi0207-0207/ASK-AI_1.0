from django.core.mail import send_mail
from django.conf import settings


def send_otp_email(user, otp):
    """
    Sends the OTP code to the user's email via Django's SMTP backend
    (configured in settings.py with your Gmail/SMTP credentials).
    Kept as a single function so the email template/copy only lives
    in one place, regardless of whether it's called from registration
    or a "resend OTP" action.
    """
    subject = "Your verification code"
    message = (
        f"Hi {user.email},\n\n"
        f"Your verification code is: {otp.code}\n"
        f"This code expires in {otp.OTP_VALIDITY_MINUTES} minutes.\n\n"
        f"If you didn't request this, you can safely ignore this email."
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
