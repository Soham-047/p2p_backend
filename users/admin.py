# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("id","full_name","username","email","secondary_email","batch","is_current_student","is_staff")
    fieldsets = UserAdmin.fieldsets + (("Extra", {"fields": ("full_name", "secondary_email", "batch", "is_current_student")}),)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id","user","updated_at")