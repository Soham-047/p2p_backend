# p2p_comm/settings.py
from pathlib import Path
from datetime import timedelta
import ssl, certifi
from decouple import config, Csv

def get_env(key, default=None, cast=str, required=False):
    """
    Get environment variable via python-decouple.
    """
    try:
        value = config(key, default=default, cast=cast)
        if required and value is None:
            raise RuntimeError(f"Required environment variable '{key}' not set.")
        return value
    except Exception as e:
        raise ValueError(f"Failed to fetch environment variable '{key}': {e}")

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY - change this in production
SECRET_KEY = get_env("SECRET_KEY", required=True)
DEBUG = get_env("DEBUG", default="False")

# Development hosts
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Application definition
INSTALLED_APPS = [
    # django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # third-party
    "rest_framework",
    "rest_framework_simplejwt",

    # email
    "anymail",

    "drf_spectacular",
    "corsheaders",

    # your apps
    "users",
    'posts',  # make sure this app exists
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # CSRF middleware stays for admin/session pages; JWT API views don't use it
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Corsheaders middleware
    "corsheaders.middleware.CorsMiddleware",
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_CREDENTIALS = True
ROOT_URLCONF = "p2p_comm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # frontend handles UI; templates not required for API
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "p2p_comm.wsgi.application"

# Database - keep SQLite for dev; switch to Postgres in prod
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Custom user model
AUTH_USER_MODEL = "users.CustomUser"

# Password validation (default validators)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"   # your local timezone
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -----------------------
# REST Framework + JWT
# -----------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "P2PComm API",
    "DESCRIPTION": "P2P communication backend API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [{"Bearer": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "Bearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
    },
}


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # default permission: authenticated for API views unless overridden per-view
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
REST_FRAMEWORK.update({
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
})
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    # add more config here if needed (algorithms, signing key, etc.)
}


# -----------------------
# Email (development)
# -----------------------
# Console backend prints emails to the runserver output for dev/testing.

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "apikey"  # this literal string
EMAIL_HOST_PASSWORD = get_env("EMAIL_API_KEY", required=True)
DEFAULT_FROM_EMAIL = get_env("EMAIL_ID", required=True)

# -----------------------
# CORS / CSRF notes (dev)
# -----------------------
# We keep CSRF middleware active for admin and any session-based endpoints.
# API clients will use JWT in Authorization header (no CSRF token required).
# If you run frontend on a different origin during development, you may need:
#   pip install django-cors-headers
# and add corsheaders to INSTALLED_APPS + middleware and set CORS_ALLOWED_ORIGINS.
# (Don't add here unless you need it.)


# CELERy TASKS

CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"

# Chaching
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",  # different DB slot than Celery
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "p2pcomm",   # namespace for your project
        "TIMEOUT": 600,            # 10 minutes default TTL
    }
}
from django.core.cache import cache

# set
cache.set("welcome_message", "Hello Redis!", timeout=60)

# get
msg = cache.get("welcome_message")  # -> "Hello Redis!"