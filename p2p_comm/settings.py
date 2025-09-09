import ssl, certifi
import dj_database_url
from pathlib import Path
from datetime import timedelta
from decouple import config
import os


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

# SECURITY
SECRET_KEY = get_env("SECRET_KEY", required=True)
DEBUG = get_env("DEBUG", default="False")
ALLOWED_HOSTS = get_env("ALLOWED_HOSTS").split(",")

# -----------------------
# Installed Apps
# -----------------------
INSTALLED_APPS = [
    'daphne',

    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "anymail",
    "drf_spectacular",
    "corsheaders",
    "django_celery_results",
    # "django_celery_beat",

    # Project apps
    'p2p_messages',
    "users",
    'posts',
    "channels",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "p2p_comm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

ASGI_APPLICATION = "p2p_comm.asgi.application"
WSGI_APPLICATION = "p2p_comm.wsgi.application"

# -----------------------
# Database
# -----------------------
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )
}

AUTH_USER_MODEL = "users.CustomUser"

# -----------------------
# Password validation
# -----------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------
# Internationalization
# -----------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# -----------------------
# Static & Media
# -----------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "user": "60/min",
    },
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
}

REST_FRAMEWORK.update({
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
})
# SIMPLE_JWT = {
#     "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
#     "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
#     "ROTATE_REFRESH_TOKENS": False,
#     "BLACKLIST_AFTER_ROTATION": False,
#     # add more config here if needed (algorithms, signing key, etc.)
# }


# -----------------------
# Email
# -----------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "apikey"
EMAIL_HOST_PASSWORD = get_env("EMAIL_API_KEY", required=True)
DEFAULT_FROM_EMAIL = get_env("EMAIL_ID", required=True)

# -----------------------
# Redis / Celery / Cache
# -----------------------
REDIS_URL = get_env(
    "REDIS_URL",
    default="redis://localhost:6379/0"
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

from urllib.parse import urlparse

parsed_url = urlparse(REDIS_URL)
ssl_opts = None
if parsed_url.scheme == "rediss":
    ssl_opts = {"ssl_cert_reqs": ssl.CERT_NONE}  # CERT_NONE avoids verification errors
    CELERY_BROKER_USE_SSL = ssl_opts
    CELERY_RESULT_BACKEND_USE_SSL = ssl_opts
else:
    CELERY_BROKER_USE_SSL = None
    CELERY_RESULT_BACKEND_USE_SSL = None

CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"


# # Caching

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
# settings.py
# settings.py
# import ssl

# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": REDIS_URL + "/0",
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#             "CONNECTION_POOL_KWARGS": {
#                 "ssl_cert_reqs": ssl.CERT_NONE,
#             },
#             "SSL": True,  # <-- this tells redis-py to actually use SSL
#         },
#     }
# }




# Cache TTLs

# -----------------------------
# JWT / DRF
# -----------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
}

# -----------------------------
# Celery app initialization
# -----------------------------
app = Celery("p2p_comm")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# settings.py

# Cache TTL values (in seconds)

CACHE_TTL_SHORT = 60       # 1 minute
CACHE_TTL_MED = 300        # 5 minutes
CACHE_TTL_LONG = 3600      # 1 hour


from celery import Celery


app = Celery("p2p_comm")
app.conf.update(timezone = 'Asia/Kolkata')
app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    redis_backend_use_ssl={
        "ssl_cert_reqs": ssl.CERT_NONE  # or CERT_REQUIRED / CERT_OPTIONAL
    },
    broker_use_ssl={
        "ssl_cert_reqs": ssl.CERT_NONE
    },
)



# p2p_comm/settings.py

# ... (at the end of the file) ...

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",  # <--- Set the level to INFO
    },
}

