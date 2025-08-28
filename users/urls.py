# users/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, RegistrationAPIView, MeProfileView, PublicProfileView, profile_avatar_view, ProfileSearchView, MeAvatarUploadView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/register/", RegistrationAPIView.as_view(), name="api-register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    path('profile/me/', MeProfileView.as_view(), name='profile-me'),
    path('profile/me/avatar/', MeAvatarUploadView.as_view(), name='profile-me-avatar-upload'),  # POST/PUT
    # path('profile/me/avatar/', me_avatar_view, name='profile-me-avatar'),
    path("profile/search/", ProfileSearchView.as_view(), name="profile-search"),
    path("profile/<str:username>/", PublicProfileView.as_view(), name="profile-public"),
    path("profile/<str:username>/avatar/", profile_avatar_view, name="profile-avatar"),
]

