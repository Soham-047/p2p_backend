# users/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    # Auth & Users
    UserViewSet,
    RegistrationAPIView,

    # Profile core
    MeProfileView,
    PublicProfileView,
    ProfileSearchView,

    # Profile sub-sections
    ExperienceViewSet,
    SkillViewSet,
    EducationViewSet,
    SocialLinkViewSet,
    ProjectViewSet,
    CertificateViewSet,
)

# Router for ViewSets
router = DefaultRouter()

# Users
router.register(r"users", UserViewSet, basename="user")

# Profile sub-models (LinkedIn-like sections)
router.register(r"profile/me/experiences", ExperienceViewSet, basename="experience")
router.register(r"profile/me/skills", SkillViewSet, basename="skill")
router.register(r"profile/me/education", EducationViewSet, basename="education")
router.register(r"profile/me/social-links", SocialLinkViewSet, basename="sociallink")
router.register(r"profile/me/projects", ProjectViewSet, basename="project")
router.register(r"profile/me/certificates", CertificateViewSet, basename="certificate")

urlpatterns = [
    # Router endpoints (users + profile sub-models)
    path("", include(router.urls)),

    # -------------------------------
    # Auth
    # -------------------------------
    path("auth/register/", RegistrationAPIView.as_view(), name="api-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # -------------------------------
    # Profile (Core)
    # -------------------------------
    path("profile/me/", MeProfileView.as_view(), name="profile-me"),

    # Search & Public Profiles
    path("profile/search/", ProfileSearchView.as_view(), name="profile-search"),
    path("profile/<str:username>/", PublicProfileView.as_view(), name="profile-public"),
]
