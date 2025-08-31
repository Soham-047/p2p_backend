# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

class CustomUser(AbstractUser):
    # keep first_name, last_name, username fields from AbstractUser
    email = models.EmailField(unique=True)
    secondary_email = models.EmailField(blank=True, null=True)
    batch = models.CharField(max_length=10, blank=True)  # e.g., "2022"
    is_current_student = models.BooleanField(default=True)  # True=current, False=alumni
    full_name = models.CharField(max_length=255, blank=True, db_index=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username
    
def avatar_upload_path(instance, filename):
    return f"avatars/{instance.user_id}/{filename}"

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    # LinkedIn-like fields
    headline = models.CharField(max_length=140, blank=True)
    about = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    # Store experiences/links as JSON (works on SQLite and Postgres)
    # experiences = models.JSONField(default=list, blank=True)  # e.g., [{"title": "...", "company": "..."}]
    links = models.JSONField(default=list, blank=True)        # e.g., [{"label":"GitHub","url":"..."}]

    updated_at = models.DateTimeField(auto_now=True)
    
    # Blob fields for storing avatar in DB
    avatar_blob = models.BinaryField(blank=True, null=True, editable=True)
    avatar_content_type = models.CharField(max_length=120, blank=True, null=True)
    avatar_filename = models.CharField(max_length=255, blank=True, null=True)
    avatar_size = models.PositiveIntegerField(blank=True, null=True)

    def has_avatar(self):
        return bool(self.avatar_blob)
    def __str__(self):
        return f"Profile<{self.user.username}>"
    
class Experience(models.Model):
    profile = models.ForeignKey("Profile", related_name="experiences", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.title} at {self.company}"


class Skill(models.Model):
    profile = models.ForeignKey("Profile", related_name="skills", on_delete=models.CASCADE)
    name = models.CharField(max_length=120, db_index=True)
    level = models.CharField(max_length=50, blank=True)  # Beginner / Intermediate / Expert

    class Meta:
        unique_together = ("profile", "name")

    def __str__(self):
        return f"{self.name} ({self.profile.user.username})"


class Education(models.Model):
    profile = models.ForeignKey("Profile", related_name="educations", on_delete=models.CASCADE)
    school = models.CharField(max_length=255)
    degree = models.CharField(max_length=255, blank=True)
    field_of_study = models.CharField(max_length=255, blank=True)
    start_year = models.PositiveIntegerField(blank=True, null=True)
    end_year = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.school} ({self.profile.user.username})"