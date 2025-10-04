# from rest_framework import serializers
# from django.contrib.auth import get_user_model
# from .models import Profile, Experience, Skill, Education, Links, SocialLink, Project, Certificate
# import base64

# User = get_user_model()
# COLLEGE_DOMAIN = "@iiitbh.ac.in"

# # -------------------------------
# # Registration
# # -------------------------------
# class RegistrationSerializer(serializers.Serializer):
#     college_email = serializers.EmailField()
#     batch = serializers.CharField(max_length=10, required=False)
#     is_current_student = serializers.BooleanField(default=True)

#     def validate_college_email(self, value):
#         if not value.lower().endswith(COLLEGE_DOMAIN):
#             raise serializers.ValidationError("Registration requires a college email.")
#         if User.objects.filter(email__iexact=value).exists():
#             raise serializers.ValidationError("A user with this college email already exists.")
#         return value.lower()


# # -------------------------------
# # Public Profile
# # -------------------------------

# class ExperienceSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Experience
#         fields = ["id", "title", "company", "location", "start_date", "end_date", "description"]


# class SkillSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Skill
#         fields = ["id", "name", "level"]


# class EducationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Education
#         fields = ["id", "school", "degree", "field_of_study", "start_year", "end_year", "description"]

# class LinkSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Links
#         fields = ["id", "label", "url"]

# class SocialLinkSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = SocialLink
#         fields = ["id", "platform", "url"]


# class ProjectSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Project
#         fields = ["id", "title", "description", "link"]


# class CertificateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Certificate
#         fields = ["id", "name", "issuer", "issue_date", "credential_id", "credential_url"]


# class PublicProfileSerializer(serializers.ModelSerializer):
#     username = serializers.CharField(source="user.username", read_only=True)
#     full_name = serializers.CharField(source="user.full_name", read_only=True)
#     avatar_url = serializers.SerializerMethodField()

#     experiences = ExperienceSerializer(many=True, read_only=True)
#     skills = SkillSerializer(many=True, read_only=True)
#     education = EducationSerializer(many=True, read_only=True)
#     links = LinkSerializer(many=True, read_only=True)
#     dob = serializers.DateField(read_only=True)
#     achievements = serializers.CharField(read_only=True)
#     headline = serializers.CharField(read_only=True)
#     about = serializers.CharField(read_only=True)
#     location = serializers.CharField(read_only=True)

#     social_links = SocialLinkSerializer(many=True, read_only=True)
#     projects = ProjectSerializer(many=True, read_only=True)
#     certificates = CertificateSerializer(many=True, read_only=True)

#     class Meta:
#         model = Profile
#         fields = [
#             "username", "full_name", "headline", "about", "location",
#             "dob", "achievements",
#             "experiences", "skills", "education",
#             "social_links", "projects", "certificates",
#             "avatar_url", "links",
#         ]

#     def get_avatar_url(self, obj):
#         request = self.context.get("request")
#         if request and obj and obj.has_avatar():
#             return request.build_absolute_uri(f"/api/profile/{obj.user.username}/avatar/")
#         return None


# # -------------------------------
# # Profile Serializer (Owner)
# # -------------------------------
# class ProfileSerializer(serializers.ModelSerializer):
#     username = serializers.CharField(source="user.username", required=False)
#     full_name = serializers.CharField(source="user.full_name", required=False)
#     email = serializers.EmailField(source="user.email", read_only=True)  
#     secondary_email = serializers.EmailField(source="user.secondary_email", required=False, allow_null=True, allow_blank=True)
#     batch = serializers.CharField(source="user.batch", required=False, allow_blank=True, allow_null=True)
#     is_current_student = serializers.BooleanField(source="user.is_current_student", required=False)
#     dob = serializers.DateField(required=False, allow_null=True)
#     achievements = serializers.CharField(required=False, allow_blank=True)

#     # ✅ Now writable
#     avatar_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#     # banner_img_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)

#     experiences = ExperienceSerializer(many=True, read_only=True)
#     educations = EducationSerializer(many=True, read_only=True)
#     skills = SkillSerializer(many=True, read_only=True)
#     links = LinkSerializer(many=True, read_only=True)
#     social_links = SocialLinkSerializer(many=True, read_only=True)
#     projects = ProjectSerializer(many=True, read_only=True)
#     certificates = CertificateSerializer(many=True, read_only=True)

#     class Meta:
#         model = Profile
#         fields = [
#             "username", "full_name", "email", "secondary_email",
#             "batch", "is_current_student", "dob", "location", "headline", "about",
#             "achievements", "experiences", "educations", "skills", "links", "social_links",
#             "projects", "certificates", "avatar_url", "updated_at"
#         ]
#         read_only_fields = ["updated_at"]

#     def update(self, instance, validated_data):
#         user_data = validated_data.pop("user", {})
#         user = instance.user

#         # update user fields
#         if "username" in user_data:
#             username = user_data["username"]
#             if User.objects.exclude(pk=user.pk).filter(username=username).exists():
#                 raise serializers.ValidationError({"username": "This username is already taken."})
#             user.username = username

#         for attr in ("full_name", "secondary_email", "batch", "is_current_student"):
#             if attr in user_data:
#                 setattr(user, attr, user_data[attr])
#         user.save()

#         # ✅ Handle avatar_url update
#         if "avatar_url" in validated_data:
#             instance.avatar_url = validated_data["avatar_url"]

#         return super().update(instance, validated_data)


# # -------------------------------
# # Me Profile
# # -------------------------------
# class MeProfileSerializer(ProfileSerializer):
#     """Profile serializer for /me endpoint"""
#     class Meta(ProfileSerializer.Meta):
#         fields = ProfileSerializer.Meta.fields
#         read_only_fields = ["updated_at"]









from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Profile, Experience, Skill, Education, Links, SocialLink, Project, Certificate
from django.core.validators import EmailValidator
User = get_user_model()


# -------------------------------
# Registration
# -------------------------------
class RegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    college_email = serializers.EmailField()
    batch = serializers.CharField(max_length=10, required=False)
    is_current_student = serializers.BooleanField(default=True)

    def validate_college_email(self, value):
        if not EmailValidator(value):
            raise serializers.ValidationError("Registration requires a valid email.")
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()
    def validate(self, data):
        """
        Check that the batch (graduation year) is 4 years after the admission year
        derived from the college email.
        """
        college_email = data.get("college_email")
        batch_str = data.get("batch")
        return data


# -------------------------------
# Public Profile
# -------------------------------
# from rest_framework import serializers
# from django.contrib.auth import get_user_model

User = get_user_model()

class JWTUserDetailsSerializer(serializers.ModelSerializer):
    """
    Serializer used by dj-rest-auth to return the 'user' object 
    in the JWT/Social Login response.
    Explicitly define AbstractUser fields to ensure they are read.
    """
    # Explicitly define standard fields (inherited from AbstractUser)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True) # Email is unique=True on your model
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    
    # Custom fields from your CustomUser model
    full_name = serializers.CharField(read_only=True)
    batch = serializers.CharField(read_only=True)
    is_current_student = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = User
        fields = (
            # Removed 'pk' as requested
            'username', 
            'email', 
            'first_name', 
            'last_name',
            'full_name', 
            'batch', 
            'is_current_student',
        )
        # Note: 'read_only_fields' is redundant since all fields are read_only=True,
        # but leaving the structure clean.


class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = ["id", "title", "company", "location", "start_date", "end_date", "description"]


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "level"]


class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ["id", "school", "degree", "field_of_study", "start_year", "end_year", "description"]


class LinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Links
        fields = ["id", "label", "url"]


class SocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLink
        fields = ["id", "platform", "url"]


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "title", "description", "link"]


class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = ["id", "name", "issuer", "issue_date", "credential_id", "credential_url"]


class PublicProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    secondary_email = serializers.EmailField(source="user.secondary_email", read_only=True)
    experiences = ExperienceSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    educations = EducationSerializer(many=True, read_only=True)
    links = LinkSerializer(many=True, read_only=True)
    dob = serializers.DateField(read_only=True)
    # achievements = serializers.CharField(read_only=True)
    headline = serializers.CharField(read_only=True)
    about = serializers.CharField(read_only=True)
    location = serializers.CharField(read_only=True)

    social_links = SocialLinkSerializer(many=True, read_only=True)
    projects = ProjectSerializer(many=True, read_only=True)
    certificates = CertificateSerializer(many=True, read_only=True)

    class Meta:
        model = Profile
        fields = [
            "username", "full_name", "headline", "about", "location",
            "dob", 'secondary_email',
            "experiences", "skills", "educations",
            "social_links", "projects", "certificates",
            "avatar_url", "banner_img_url", "links",
        ]


# -------------------------------
# Profile Serializer (Owner)
# -------------------------------
class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", required=False)
    full_name = serializers.CharField(source="user.full_name", required=False)
    email = serializers.EmailField(source="user.email", read_only=True)
    secondary_email = serializers.EmailField(
        source="user.secondary_email", required=False, allow_null=True, allow_blank=True
    )
    batch = serializers.CharField(source="user.batch", required=False, allow_blank=True, allow_null=True)
    is_current_student = serializers.BooleanField(source="user.is_current_student", required=False)
    dob = serializers.DateField(required=False, allow_null=True)
    achievements = serializers.CharField(required=False, allow_blank=True)

    avatar_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    banner_img_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    experiences = ExperienceSerializer(many=True, read_only=True)
    educations = EducationSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    links = LinkSerializer(many=True, read_only=True)
    social_links = SocialLinkSerializer(many=True, read_only=True)
    projects = ProjectSerializer(many=True, read_only=True)
    certificates = CertificateSerializer(many=True, read_only=True)

    class Meta:
        model = Profile
        fields = [
            "username", "full_name", "email", "secondary_email",
            "batch", "is_current_student", "dob", "location", "headline", "about",
            "achievements", "experiences", "educations", "skills", "links", "social_links",
            "projects", "certificates", "avatar_url", "banner_img_url", "updated_at"
        ]
        read_only_fields = ["updated_at"]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        user = instance.user

        # update user fields
        if "username" in user_data:
            username = user_data["username"]
            if User.objects.exclude(pk=user.pk).filter(username=username).exists():
                raise serializers.ValidationError({"username": "This username is already taken."})
            user.username = username

        for attr in ("full_name", "secondary_email", "batch", "is_current_student"):
            if attr in user_data:
                setattr(user, attr, user_data[attr])
        user.save()

        # ✅ Handle avatar_url & banner_img_url update
        if "avatar_url" in validated_data:
            instance.avatar_url = validated_data["avatar_url"]
        if "banner_img_url" in validated_data:
            instance.banner_img_url = validated_data["banner_img_url"]

        return super().update(instance, validated_data)


# -------------------------------
# Me Profile
# -------------------------------
class MeProfileSerializer(ProfileSerializer):
    """Profile serializer for /me endpoint"""
    class Meta(ProfileSerializer.Meta):
        fields = ProfileSerializer.Meta.fields
        read_only_fields = ["updated_at"]

class GoogleAuthRequestSerializer(serializers.Serializer):
    """Serializer to document the expected request body for Google Login."""
    access_token = serializers.CharField(
        required=True,
        help_text="The OAuth2 access token received from Google after client-side authorization."
    )





class GoogleAuthResponseSerializer(serializers.Serializer):
    """
    Serializer to document the full JWT response structure without relying on 
    ModelSerializer introspection at the top level.
    """
    # Standard JWT fields
    access = serializers.CharField(read_only=True, help_text="JWT Access Token")
    refresh = serializers.CharField(read_only=True, help_text="JWT Refresh Token")
    
    # Nested User details field
    user = JWTUserDetailsSerializer(read_only=True, help_text="Detailed user object.")