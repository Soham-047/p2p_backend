# users/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from rest_framework.decorators import api_view, permission_classes
from .serializers import (
    RegistrationSerializer,
    ProfileSerializer,
    PublicProfileSerializer,
    MeProfileSerializer,
    ExperienceSerializer, SkillSerializer, EducationSerializer,
    LinkSerializer, SocialLinkSerializer, ProjectSerializer, CertificateSerializer
)
from .models import Profile, Experience, Skill, Education, Links, SocialLink, Project, Certificate
from .utils import make_username_from_email, make_random_password
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.generics import RetrieveAPIView, ListAPIView
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.db.models import Q
from users.tasks import send_registration_email, log_user_activity
from rest_framework import serializers
User = get_user_model()


# -------------------------------
# Registration
# -------------------------------
class RegistrationAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    
    
    
    @extend_schema(
        summary="Register a new student",
        description="Register with a **college email** (must end with `@iiitbh.ac.in`). "
                    "A username and password are generated and sent via email.",
        request=RegistrationSerializer,
        responses={
            201: OpenApiResponse(description="Registered. Credentials emailed."),
            400: OpenApiResponse(description="Validation error")
        },
        tags=["Auth"],
    )
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        full_name = serializer.validated_data["full_name"]
        college_email = serializer.validated_data["college_email"]
        batch = serializer.validated_data.get("batch", "")
        is_current = serializer.validated_data.get("is_current_student", True)

        username = make_username_from_email(college_email)
        password = make_random_password()

        user = User.objects.create_user(username=username, email=college_email)
        user.set_password(password)
        user.full_name = full_name
        user.batch = batch
        user.is_current_student = is_current
        user.save()

        send_registration_email.delay(
            subject="Your P2PComm credentials",
            message=f"Hello,\n\nYour account has been created.\n\nUsername: {username}\nPassword: {password}\n\nLogin at /login/.",
            to_email=college_email,
        )

        return Response(
            {"detail": "Registered. Credentials emailed."},
            status=status.HTTP_201_CREATED,
            headers={"Location": "/api/auth/login/"}
        )


# -------------------------------
# User ViewSet
# -------------------------------
@extend_schema(tags=["Users"])
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = None

    @extend_schema(summary="List all users (admin only)")
    def list(self, request):
        if not request.user.is_staff:
            return Response({"detail": "Not allowed"}, status=403)
        data = [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "secondary_email": u.secondary_email,
                "batch": u.batch,
                "is_current_student": u.is_current_student,
            }
            for u in self.get_queryset()
        ]
        return Response(data)

    @extend_schema(summary="Retrieve a user")
    def retrieve(self, request, pk=None):
        try:
            u = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(status=404)

        if request.user.is_staff or request.user.pk == u.pk:
            return Response({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "secondary_email": u.secondary_email,
                "batch": u.batch,
                "is_current_student": u.is_current_student,
            })
        return Response({"detail": "Not allowed"}, status=403)


# -------------------------------
# Me Profile
# -------------------------------
class MeProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        summary="Get my profile",
        description="Retrieve the authenticated user's profile.",
        responses=MeProfileSerializer,
        tags=["Profile"],
    )
    def get(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = MeProfileSerializer(profile, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Update my profile",
        description="Partially update the authenticated user's profile.",
        request=MeProfileSerializer,
        responses=MeProfileSerializer,
        tags=["Profile"],
    )
    def patch(self, request):
        serializer = MeProfileSerializer(
            request.user.profile,
            data=request.data,
            partial=True,
            context={"request": request}
        )
        if serializer.is_valid():
            profile = serializer.save()
            log_user_activity.delay(
                request.user.id,
                f"Updated profile: {', '.join(serializer.validated_data.keys())}"
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


# -------------------------------
# Public Profile
# -------------------------------
@extend_schema(tags=["Profile"])
class PublicProfileView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicProfileSerializer
    lookup_field = "username"

    @extend_schema(
        summary="Get public profile by username",
        description="Retrieve a user's public profile by username.",
        responses=PublicProfileSerializer,
    )
    def get_object(self):
        username = self.kwargs.get("username")
        user = get_object_or_404(User, username=username)
        profile, _ = Profile.objects.get_or_create(user=user)
        return profile

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


@extend_schema(tags=["Profile"])
class ProfileSearchView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicProfileSerializer

    @extend_schema(
        summary="Search profiles",
        description="Search users by full name or username. "
                    "Supports a `q` query param and `limit` (max 50).",
        responses=PublicProfileSerializer(many=True),
    )
    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        limit = min(max(int(self.request.query_params.get("limit", 20)), 1), 50)
        if not q:
            return Profile.objects.none()
        return Profile.objects.select_related("user").filter(
            Q(user__full_name__icontains=q) | Q(user__username__icontains=q)
        ).order_by("user__full_name", "user__username")[:limit]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


# -------------------------------
# Profile Sub-Models CRUD
# -------------------------------
@extend_schema(tags=["Profile - Experience"])
class ExperienceViewSet(viewsets.ModelViewSet):
    serializer_class = ExperienceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Experience.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(tags=["Profile - Skills"])
class SkillViewSet(viewsets.ModelViewSet):
    serializer_class = SkillSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Skill.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(tags=["Profile - Education"])
class EducationViewSet(viewsets.ModelViewSet):
    serializer_class = EducationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Education.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(tags=["Profile - Projects"])
class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(tags=["Profile - Certificates"])
class CertificateViewSet(viewsets.ModelViewSet):
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Certificate.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


@extend_schema(tags=["Profile - Social Links"])
class SocialLinkViewSet(viewsets.ModelViewSet):
    serializer_class = SocialLinkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SocialLink.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)
