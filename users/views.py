# users/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from rest_framework.decorators import api_view, permission_classes
from .serializers import RegistrationSerializer, ProfileSerializer, PublicProfileSerializer, MeProfileSerializer, AvatarSerializer
from .models import Profile
from .utils import make_username_from_email, make_random_password
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.generics import RetrieveAPIView, ListAPIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from io import BytesIO
from django.http import HttpResponse, Http404
from rest_framework import status
from django.db.models import Q
from users.tasks import send_registration_email, log_user_activity
import base64
from PIL import Image
from .models import Experience, Skill, Education, Links, SocialLink, Project, Certificate
from .serializers import ExperienceSerializer, SkillSerializer, EducationSerializer, LinkSerializer, SocialLinkSerializer, ProjectSerializer, CertificateSerializer
User = get_user_model()

class RegistrationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Register a new student (college email required)",
        description="Create a student account using only the college email. "
                    "The server generates a username and password and emails credentials to the college email.",
        request=RegistrationSerializer,
        responses={
            201: OpenApiResponse(description="Registered. Credentials emailed to college email."),
            400: OpenApiResponse(description="Validation error")
        },
        tags=["Auth"],
        examples=[
            OpenApiExample(
                "Example request",
                value={"college_email": "student@iiitbh.ac.in", "batch": "2025", "is_current_student": True},
                request_only=True,
                response_only=False,
            )
        ],
    )
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        college_email = serializer.validated_data["college_email"]
        batch = serializer.validated_data.get("batch", "")
        is_current = serializer.validated_data.get("is_current_student", True)

        # Generate username and password
        username = make_username_from_email(college_email)
        password = make_random_password()

        # Create user
        user = User.objects.create_user(username=username, email=college_email)
        user.set_password(password)
        user.batch = batch
        user.is_current_student = is_current
        user.save()

        # Email credentials to college email (console backend in dev)
        send_registration_email.delay(
            subject="Your P2PComm credentials",
            message=f"Hello,\n\nYour account has been created.\n\nUsername: {username}\nPassword: {password}\n\nPlease login at /login/ and complete your profile.",
            to_email=college_email,   # ✅ matches task signature
        )

        # Return 201 with location pointing to login page (frontend handles redirect)
        return Response(
            {"detail": "Registered. Credentials emailed to your college email."},
            status=status.HTTP_201_CREATED,
            headers={"Location": "/api/auth/login/"}
        )

# class CompleteProfileView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         serializer = CompleteProfileSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         user = request.user
#         user.secondary_email = serializer.validated_data["secondary_email"]
#         user.batch = serializer.validated_data["batch"]
#         user.is_current_student = serializer.validated_data["is_current_student"]
#         user.save()
#         return Response({"detail":"Profile updated"}, status=status.HTTP_200_OK)

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset: list and retrieve users (admins can expand).
    """
    queryset = User.objects.all()
    serializer_class = None  # we'll return basic dicts for brevity

    @extend_schema(
        summary="List users (admin only)",
        description="Return a list of users. Accessible only to staff accounts.",
        responses={200: OpenApiResponse(description="List of users"), 403: OpenApiResponse(description="Not allowed")},
        tags=["Users"],
    )
    def list(self, request):
        # minimal user list for admins
        if not request.user.is_staff:
            return Response({"detail":"Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        qs = self.get_queryset()
        data = [{"id":u.id, "username":u.username, "email":u.email, "secondary_email":u.secondary_email, "batch":u.batch, "is_current_student":u.is_current_student} for u in qs]
        return Response(data)
    
    @extend_schema(
        summary="Retrieve user (self or admin)",
        description="Retrieve a single user's basic info. Admins can fetch any user; regular users only their own record.",
        responses={200: OpenApiResponse(description="User object"), 403: OpenApiResponse(description="Not allowed"), 404: OpenApiResponse(description="Not found")},
        parameters=[OpenApiParameter(name="pk", description="User primary key", required=True, type=int)],
        tags=["Users"],
    )
    
    def retrieve(self, request, pk=None):
        try:
            u = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if request.user.is_staff or request.user.pk == u.pk:
            data = {"id":u.id, "username":u.username, "email":u.email, "secondary_email":u.secondary_email, "batch":u.batch, "is_current_student":u.is_current_student}
            return Response(data)
        return Response({"detail":"Not allowed"}, status=status.HTTP_403_FORBIDDEN)


class MeProfileView(APIView):
    """
    GET  /api/profile/me/     -> current user's profile
    PATCH /api/profile/me/    -> update current user's profile
    Accepts JSON or multipart (for avatar)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        summary="Get current user's profile",
        description="Returns the authenticated user's profile.",
        responses={200: MeProfileSerializer},
        tags=["Profile"]
    )
    def get(self, request, *args, **kwargs):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = MeProfileSerializer(profile)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Update current user's profile",
        description="Partial update to profile (PATCH). Supports multipart for avatar or base64 payload.",
        request=MeProfileSerializer,
        responses={200: MeProfileSerializer},
        tags=["Profile"],
    )
    def patch(self, request, *args, **kwargs):
        serializer = MeProfileSerializer(
    request.user.profile, data=request.data, partial=True, context={"request": request}
)


        if serializer.is_valid():
            profile = serializer.save()

            # ✅ send activity log asynchronously
            log_user_activity.delay(
                request.user.id,
                f"Updated profile: {', '.join(serializer.validated_data.keys())}"
            )

            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    



class PublicProfileView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicProfileSerializer   # use public serializer here
    lookup_field = "username"

    def get_object(self):
        username = self.kwargs.get("username")
        user = get_object_or_404(User, username=username)
        profile, _ = Profile.objects.get_or_create(user=user)
        return profile

    @extend_schema(
        summary="Get public profile by username",
        responses={200: PublicProfileSerializer, 404: OpenApiResponse(description="Not found")},
        tags=["Profile"],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


@extend_schema(
    summary="Search public profiles by full name or username",
    parameters=[
        OpenApiParameter(
            name="q",
            description="Full name or username (substring, case-insensitive)",
            required=True,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name="limit",
            description="Max results (default 20, max 50)",
            required=False,
            type=int,
            location=OpenApiParameter.QUERY
        ),
    ],
    responses={200: PublicProfileSerializer(many=True)},
    tags=["Profile"],
)
class ProfileSearchView(ListAPIView):
    """
    GET /api/profile/search/?q=<name or username>
    Returns public profiles matching full_name (primary) or username (secondary).
    """
    permission_classes = [AllowAny]
    serializer_class = PublicProfileSerializer

    # @extend_schema(
    #     summary="Search public profiles by full name or username",
    #     parameters=[
    #         OpenApiParameter(name="q", description="Full name or username (substring, case-insensitive)", required=True, type=str),
    #         OpenApiParameter(name="limit", description="Max results (default 20, max 50)", required=False, type=int),
    #     ],
    #     responses={200: PublicProfileSerializer(many=True)},
    #     tags=["Profile"],
    # )
    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        limit = min(max(int(self.request.query_params.get("limit", 20)), 1), 50)
        if not q:
            return Profile.objects.none()

        # Join across user for name/username
        qs = Profile.objects.select_related("user").filter(
            Q(user__full_name__icontains=q) | Q(user__username__icontains=q)
        ).order_by("user__full_name", "user__username")[:limit]
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

# Serve avatar binary from DB. Public or protected depending on your policy (here we keep public)
@extend_schema(
    summary="Get user's avatar image",
    description="Returns the avatar image bytes with proper Content-Type.",
    responses={200: OpenApiResponse(description="image bytes")},
    tags=["Profile"]
)
def profile_avatar_view(request, username):
    user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=user)
    if not profile.has_avatar():
        raise Http404("No avatar")
    content = profile.avatar_blob
    ct = profile.avatar_content_type or "application/octet-stream"
    resp = HttpResponse(content, content_type=ct)
    # optionally set Content-Disposition if you want it downloaded:
    # resp['Content-Disposition'] = f'inline; filename="{profile.avatar_filename}"'
    return resp

@extend_schema(
    summary="Upload/Update avatar",
    description="Upload an avatar image using multipart form (key=`avatar`) or base64 string (`avatar_base64`).",
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "avatar": {"type": "string", "format": "binary"},
                "avatar_base64": {"type": "string", "example": "iVBORw0KGgoAAAANSUhEUg..."}
            },
        },
        "application/json": {
            "type": "object",
            "properties": {
                "avatar_base64": {"type": "string", "example": "iVBORw0KGgoAAAANSUhEUg..."}
            }
        }
    },
    responses={
        200: OpenApiExample(
            "Success Response",
            value={"detail": "Avatar updated successfully"}
        ),
        400: OpenApiExample(
            "Error Response",
            value={"detail": "Invalid base64 or no avatar provided"}
        )
    },
    tags=["Profile"]
)

class MeAvatarUploadView(APIView):
    """
    Manage the current user's avatar (upload, retrieve).
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        summary="Upload or update current user's avatar",
        description="Upload a new avatar image (file upload or base64 JSON). "
                    "Validates size and type. Overwrites any existing avatar.",
        request=AvatarSerializer,
        responses={
            200: OpenApiResponse(description="Avatar updated successfully"),
            400: OpenApiResponse(description="Invalid input"),
        },
        tags=["Profile"]
    )
    def post(self, request):
        serializer = AvatarSerializer(
            instance=request.user.profile,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            log_user_activity.delay(request.user.id, "Updated avatar")
            return Response({"detail": "Avatar updated successfully"}, status=200)
        return Response(serializer.errors, status=400)

    @extend_schema(
        summary="Get current user's avatar",
        description="Returns the avatar binary stream if uploaded, else 404.",
        responses={200: {"content": {"image/*": {}}},
                   404: {"description": "No avatar"}},
        tags=["Profile"]
    )
    def get(self, request):
        profile = request.user.profile
        if not profile.has_avatar():
            raise Http404("No avatar")

        response = HttpResponse(
            profile.avatar_blob,
            content_type=profile.avatar_content_type or "application/octet-stream"
        )
        # Ensures browser treats it as an inline image (renders instead of download prompt)
        response['Content-Disposition'] = (
            f'inline; filename="{profile.avatar_filename or "avatar"}"'
        )
        return response
    
class MeAvatarThumbnailView(APIView):
    """
    Returns a resized thumbnail version of the current user's avatar.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get current user's avatar thumbnail",
        description="Returns a resized thumbnail (default 128x128) of the user's avatar.",
        responses={200: {"content": {"image/*": {}}},
                   404: {"description": "No avatar"}},
        tags=["Profile"]
    )
    def get(self, request, size: int = 128):
        profile = request.user.profile
        if not profile.has_avatar():
            raise Http404("No avatar")

        # Load avatar into Pillow
        try:
            img = Image.open(BytesIO(profile.avatar_blob))
            img = img.convert("RGB")  # Ensure consistent format
            img.thumbnail((size, size))
        except Exception:
            raise Http404("Corrupted avatar image")

        # Save resized version to buffer
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type="image/jpeg")
        response['Content-Disposition'] = f'inline; filename="avatar_thumbnail.jpg"'
        return response
    
@extend_schema(
    tags=["Profile"],
    summary="Manage work experiences",
    description="CRUD operations for the authenticated user's work experiences."
)
class ExperienceViewSet(viewsets.ModelViewSet):
    serializer_class = ExperienceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Experience.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(
    tags=["Profile"],
    summary="Manage skills",
    description="CRUD operations for the authenticated user's skills."
)
class SkillViewSet(viewsets.ModelViewSet):
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Skill.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(
    tags=["Profile"],
    summary="Manage education records",
    description="CRUD operations for the authenticated user's education."
)
class EducationViewSet(viewsets.ModelViewSet):
    serializer_class = EducationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Education.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(
    tags=["Profile"],
    summary="Manage projects",
    description="CRUD operations for the authenticated user's projects."
)
class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(
    tags=["Profile"],
    summary="Manage certificates",
    description="CRUD operations for the authenticated user's certificates."
)
class CertificateViewSet(viewsets.ModelViewSet):
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Certificate.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(
    tags=["Profile"],
    summary="Manage social links",
    description="CRUD operations for the authenticated user's social links (e.g., LinkedIn, GitHub, Twitter)."
)
class SocialLinkViewSet(viewsets.ModelViewSet):
    serializer_class = SocialLinkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SocialLink.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)