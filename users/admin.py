from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile, Links, Experience, Skill, Education


# --------------------
# Inlines for Profile
# --------------------
class LinksInline(admin.TabularInline):
    model = Links
    extra = 1


class ExperienceInline(admin.StackedInline):  # use TabularInline if you prefer compact
    model = Experience
    extra = 1


class SkillInline(admin.TabularInline):
    model = Skill
    extra = 1


class EducationInline(admin.StackedInline):
    model = Education
    extra = 1


# --------------------
# CustomUser admin
# --------------------
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "id", "full_name", "username", "email",
        "secondary_email", "batch", "is_current_student", "is_active", "is_staff", "is_superuser",
    )

    fieldsets = (
    (None, {"fields": ("username", "password")}),
    ("Personal info", {
        "fields": ("full_name", "email", "secondary_email", "batch", "is_current_student")
    }),
    ("Permissions", {
        "fields": ("is_active", "is_staff", "is_superuser"),
    }),
    ("Important dates", {"fields": ("last_login", "date_joined")}),
)


    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "password1", "password2",
                "full_name", "email", "secondary_email", "batch", "is_current_student", "is_active"
            ),
        }),
    )


# --------------------
# Profile admin with inlines
# --------------------
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "updated_at")
    inlines = [LinksInline, ExperienceInline, SkillInline, EducationInline]
