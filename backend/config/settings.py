import os

from django.core.exceptions import ImproperlyConfigured
from psycopg import IsolationLevel


DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in {"true", "1"}
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY is required when DEBUG is false.")
    SECRET_KEY = "development-only-insecure-key"

ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"
).split(",")
INSTALLED_APPS = ["rest_framework", "corsheaders", "src.infrastructure.persistence.PersistenceConfig"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "habicapital"),
        "USER": os.environ.get("POSTGRES_USER", "habicapital"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "local-development-only"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        # Application use cases own transactions; HTTP requests must not open them.
        "ATOMIC_REQUESTS": False,
        "OPTIONS": {
            # Future concurrency control relies on explicit row locks.
            "isolation_level": IsolationLevel.READ_COMMITTED,
            "connect_timeout": 5,
        },
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
APP_VERSION = "0.1.0"
