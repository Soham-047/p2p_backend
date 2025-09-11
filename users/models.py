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

    headline = models.CharField(max_length=140, blank=True)
    about = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    achievements = models.TextField(null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    certificate = models.CharField(max_length=255, null=True, blank=True)
    project = models.CharField(max_length=255, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    # Avatar fields...
    # avatar_blob = models.BinaryField(blank=True, null=True, editable=True)
    # avatar_content_type = models.CharField(max_length=120, blank=True, null=True)
    # avatar_filename = models.CharField(max_length=255, blank=True, null=True)
    # avatar_size = models.PositiveIntegerField(blank=True, null=True)
    avatar_url = models.CharField(max_length=255, blank=True, null=True)
    banner_img_url = models.CharField(max_length=255, blank=True, null=True)
    def has_avatar(self):
        return bool(self.avatar_url)

    def __str__(self):
        return f"Profile<{self.user.username}>"


# ✅ Links (reuse Links but expand for social/projects/certs)
class SocialLink(models.Model):
    profile = models.ForeignKey("Profile", related_name="social_links", on_delete=models.CASCADE)
    platform = models.CharField(max_length=120)  # "LinkedIn", "GitHub", "Twitter"
    url = models.URLField()


class Project(models.Model):
    profile = models.ForeignKey("Profile", related_name="projects", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    link = models.URLField(blank=True)


class Certificate(models.Model):
    profile = models.ForeignKey("Profile", related_name="certificates", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    issuer = models.CharField(max_length=255, blank=True)
    issue_date = models.DateField(blank=True, null=True)
    credential_id = models.CharField(max_length=255, blank=True, null=True)
    credential_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.profile.user.username})"


class Links(models.Model):
    profile = models.ForeignKey("Profile", related_name="links", on_delete=models.CASCADE)
    label = models.CharField(max_length=120)
    url = models.URLField()

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