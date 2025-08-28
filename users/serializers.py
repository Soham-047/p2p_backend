# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Profile
import base64

User = get_user_model()
COLLEGE_DOMAIN = "@iiitbh.ac.in"  # enforce college domain

# -------------------------------
# Registration
# -------------------------------
class RegistrationSerializer(serializers.Serializer):
    college_email = serializers.EmailField()
    batch = serializers.CharField(max_length=10, required=False)
    is_current_student = serializers.BooleanField(default=True)

    def validate_college_email(self, value):
        if not value.lower().endswith(COLLEGE_DOMAIN):
            raise serializers.ValidationError("Registration requires a college email.")
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this college email already exists.")
        return value.lower()


# -------------------------------
# Avatar constraints
# -------------------------------
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB
ALLOWED_AVATAR_TYPES = ["image/jpeg", "image/png", "image/webp"]


# -------------------------------
# Public profile serializer
# -------------------------------
class PublicProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    avatar_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "username", "full_name",
            "headline", "about", "location",
            "experiences", "links",
            "avatar_url",
        ]

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj and obj.has_avatar():
            return request.build_absolute_uri(f"/api/profile/{obj.user.username}/avatar/")
        return None


# -------------------------------
# Full profile serializer (editable by owner)
# -------------------------------
class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", required=False)
    full_name = serializers.CharField(source="user.full_name", required=False)
    email = serializers.EmailField(source="user.email", read_only=True)  
    secondary_email = serializers.EmailField(source="user.secondary_email", required=False, allow_null=True, allow_blank=True)
    batch = serializers.CharField(source="user.batch", required=False, allow_blank=True, allow_null=True)
    is_current_student = serializers.BooleanField(source="user.is_current_student", required=False)

    # File upload or base64
    avatar = serializers.ImageField(write_only=True, required=False, allow_null=True)
    avatar_base64 = serializers.CharField(write_only=True, required=False, allow_null=True)

    avatar_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "username", "full_name", "email", "secondary_email",
            "batch", "is_current_student",
            "headline", "about", "location",
            "experiences", "links",
            "avatar", "avatar_base64", "avatar_url", "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj and obj.has_avatar():
            return request.build_absolute_uri(f"/api/profile/{obj.user.username}/avatar/")
        return None

    def validate(self, data):
        avatar_file = data.get("avatar")
        avatar_b64 = data.get("avatar_base64")

        if avatar_file:
            ct = getattr(avatar_file, "content_type", None)
            size = getattr(avatar_file, "size", 0)
            if ct not in ALLOWED_AVATAR_TYPES:
                raise serializers.ValidationError({"avatar": "Unsupported avatar file type."})
            if size > MAX_AVATAR_SIZE:
                raise serializers.ValidationError({"avatar": "Avatar too large (max 2MB)."})
        elif avatar_b64:
            try:
                if avatar_b64.startswith("data:"):
                    header, b64data = avatar_b64.split(",", 1)
                    content_type = header.split(";")[0].split(":")[1]
                else:
                    b64data = avatar_b64
                    content_type = None
                decoded = base64.b64decode(b64data)
                if len(decoded) > MAX_AVATAR_SIZE:
                    raise serializers.ValidationError({"avatar_base64": "Avatar too large (max 2MB)."})
                if content_type and content_type not in ALLOWED_AVATAR_TYPES:
                    raise serializers.ValidationError({"avatar_base64": "Unsupported avatar file type."})
            except Exception:
                raise serializers.ValidationError({"avatar_base64": "Invalid base64 image."})

        return data

    def update(self, instance, validated_data):
        # Handle nested user fields
        user_data = validated_data.pop("user", {})
        user = instance.user

        if "username" in user_data:
            username = user_data["username"]
            if User.objects.exclude(pk=user.pk).filter(username=username).exists():
                raise serializers.ValidationError({"username": "This username is already taken."})
            user.username = username

        for attr in ("full_name", "secondary_email", "batch", "is_current_student"):
            if attr in user_data:
                setattr(user, attr, user_data[attr])
        user.save()

        # Handle avatar update
        avatar_file = validated_data.pop("avatar", None)
        avatar_b64 = validated_data.pop("avatar_base64", None)

        if avatar_file:
            instance.avatar_blob = avatar_file.read()
            instance.avatar_content_type = avatar_file.content_type
            instance.avatar_filename = avatar_file.name
            instance.avatar_size = avatar_file.size
        elif avatar_b64:
            if avatar_b64.startswith("data:"):
                header, b64data = avatar_b64.split(",", 1)
                content_type = header.split(";")[0].split(":")[1]
            else:
                b64data = avatar_b64
                content_type = None
            decoded = base64.b64decode(b64data)
            instance.avatar_blob = decoded
            instance.avatar_content_type = content_type
            instance.avatar_filename = "avatar_b64_upload"
            instance.avatar_size = len(decoded)

        return super().update(instance, validated_data)

class MeProfileSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    username = serializers.CharField(source="user.username", required=False)
    full_name = serializers.CharField(source="user.full_name", required=False)
    email = serializers.EmailField(source="user.email", read_only=True)  
    secondary_email = serializers.EmailField(source="user.secondary_email", required=False, allow_null=True, allow_blank=True)
    batch = serializers.CharField(source="user.batch", required=False, allow_blank=True, allow_null=True)
    is_current_student = serializers.BooleanField(source="user.is_current_student", required=False)
    class Meta:
        model = Profile
        fields = [
            'user', "username", "full_name", "email", "secondary_email",
            "batch", "is_current_student",
            "headline", "about", "location",
            "experiences", "links", "updated_at",
        ]
        read_only_fields = ["updated_at"]

class AvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["avatar_blob", "avatar_content_type", "avatar_filename", "avatar_size"]
        read_only_fields = ["avatar_content_type", "avatar_filename", "avatar_size"]
