"""
URL configuration for p2p_comm project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# p2p_comm/urls.py
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.conf import settings
from django.conf.urls.static import static
# your_project/urls.py

from django.contrib import admin
from django.urls import path, include
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
 
# This view handles the final step where the authorization code is exchanged for tokens
# p2p_comm/urls.py
from allauth.socialaccount import views as socialaccount_views 
# ... imports ...
from drf_spectacular.utils import extend_schema, OpenApiResponse
from drf_spectacular.openapi import AutoSchema # <--- ENSURE THIS IS IMPORTED
from users.serializers import GoogleAuthRequestSerializer, GoogleAuthResponseSerializer 
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from django.conf import settings # For settings.GOOGLE_CALLBACK_URL
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
# This view handles the final step where the authorization code is exchanged for tokens
@extend_schema(
    summary="Google Social Login (Exchange Token)",
    description="Exchanges the client-side Google OAuth2 access token for JWT access/refresh tokens.",
    request=GoogleAuthRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=GoogleAuthResponseSerializer,
            description="Login successful. Returns JWT and user data."
        ),
        400: OpenApiResponse(
            description="Bad request (e.g., invalid token, user already exists with different provider)."
        )
    },
    tags=["Auth - Social"]
)
# This keeps the CSRF fix you correctly implemented
@method_decorator(csrf_exempt, name='dispatch')
class GoogleLogin(SocialLoginView):
    # CRITICAL FIX: OVERRIDE THE INHERITED SCHEMA ATTRIBUTE (Keep this for spectacular)
    schema = AutoSchema() 
    
    adapter_class = GoogleOAuth2Adapter
    # Use the dynamic URL from your settings file
    callback_url = settings.GOOGLE_CALLBACK_URL 
    
    # ❌ FIX THE TYPE ERROR: REMOVE THIS LINE
    # client_class = OAuth2Client 

urlpatterns = [
    path("admin/", admin.site.urls),


    # path('api/auth/', include('dj_rest_auth.urls')),
    # path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    # path('api/auth/google/', GoogleLogin.as_view(), name='google_login'),
    # path('accounts/', include('allauth.urls')),

    # Standard dj-rest-auth URLs
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    
    # CRITICAL: Include the full allauth URLs under a separate path.
    # This path contains the actual, correct callback view, regardless of its internal name.
    # Your specific GoogleLogin view for the POST request (remains separate)
    path('api/auth/google/', GoogleLogin.as_view(), name='google_login'),
    path('accounts/', include('allauth.urls')), 
    


    path("api/users-app/", include("users.urls")),
    path("api/posts-app/", include("posts.urls")),
    path("api/messages-app/", include("p2p_messages.urls")),
    # OpenAPI schema + UIs:
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
