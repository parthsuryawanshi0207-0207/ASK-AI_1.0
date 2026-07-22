from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, OTP


class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "is_verified", "is_staff", "is_active"]
    list_filter = ["is_verified", "is_staff", "is_active"]
    search_fields = ["email"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Status",
            {"fields": ("is_verified", "is_active", "is_staff", "is_superuser")},
        ),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_verified",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ["user", "code", "created_at", "expires_at", "is_used"]
    list_filter = ["is_used"]
    search_fields = ["user__email"]


admin.site.register(User, UserAdmin)
