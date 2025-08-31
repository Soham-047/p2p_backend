# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "id", "full_name", "username", "email",
        "secondary_email", "batch", "is_current_student", "is_active"
    )

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {
            "fields": ("full_name", "email", "secondary_email", "batch", "is_current_student")
        }),
        ("Status", {"fields": ("is_active",)}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "full_name", "email", "secondary_email", "batch", "is_current_student", "is_active"),
        }),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id","user","updated_at")