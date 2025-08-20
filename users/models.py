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
    experiences = models.JSONField(default=list, blank=True)  # e.g., [{"title": "...", "company": "..."}]
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

@receiver(post_save, sender=CustomUser)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
