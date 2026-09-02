import os as _os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = _os.getenv("SECRET_KEY", "django-insecure-change-me-for-production")
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Absolute base URL used for push-notification payloads and reminder emails.
BASE_URL = _os.getenv("BASE_URL", "http://127.0.0.1:8000")

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://*.ngrok-free.app",
    "https://*.ngrok.io",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "core_system",
    "django.contrib.staticfiles",
    "channels",
    "django_browser_reload",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
    "core_system.middleware.NoCacheMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "core_system.middleware.ZeroTrustMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

X_FRAME_OPTIONS = "SAMEORIGIN"

ROOT_URLCONF = "caufa_portal.urls"
# Inside caufa_portal/settings.py

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            # ADD THIS BLOCK BELOW TO GLOBALLY ENABLE LOAD STATIC
            "builtins": [
                "django.templatetags.static",
            ],
        },
    },
]

WSGI_APPLICATION = "caufa_portal.wsgi.application"
ASGI_APPLICATION = "caufa_portal.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "caufa-cache",
        "TIMEOUT": 300,
    }
}

# Prefer MySQL for local development so the project connects to your SQLyog/
# MySQL server by default. SQLite is only used when explicitly enabled.
USE_SQLITE_FALLBACK = _os.getenv("USE_SQLITE_FALLBACK", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if USE_SQLITE_FALLBACK:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": _os.getenv("DB_NAME", "capstone_project_db"),
            "USER": _os.getenv("DB_USER", "root"),
            "PASSWORD": _os.getenv("DB_PASSWORD", "loleris1234"),
            "HOST": _os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": _os.getenv("DB_PORT", "3306"),
            "OPTIONS": {
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media upload configuration (receipts / supporting proofs)
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication Redirect routing boundaries
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# -------------------------
# Django Email Settings (read from .env)
# -------------------------
EMAIL_BACKEND = _os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = _os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(_os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = _os.getenv("EMAIL_USE_TLS", "true").lower() in {"1", "true", "yes"}
EMAIL_HOST_USER = _os.getenv("EMAIL_HOST_USER", "vergarajustin636@gmail.com")
EMAIL_HOST_PASSWORD = _os.getenv("EMAIL_HOST_PASSWORD", "kzct frrc uhga fqlm")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or "noreply@isucaufa.org"

# -------------------------
# Gmail SMTP (for notifications)
# -------------------------
# Add these to your environment (recommended via .env + python-dotenv) or set them directly.
# Expected values for Gmail SMTP:
# - GMAIL_SMTP_HOST: smtp.gmail.com
# - GMAIL_SMTP_PORT: 587
# - GMAIL_SMTP_USER: your_gmail_address
# - GMAIL_SMTP_PASSWORD: your Gmail App Password
# - GMAIL_SMTP_USE_TLS: true (optional; default True)
#
# If you already set Django's EMAIL_* settings, we fall back to them.

# Host/port
GMAIL_SMTP_HOST = _os.getenv("GMAIL_SMTP_HOST", _os.getenv("EMAIL_HOST", "smtp.gmail.com"))
GMAIL_SMTP_PORT = int(_os.getenv("GMAIL_SMTP_PORT", _os.getenv("EMAIL_PORT", "587")))

# Credentials
GMAIL_SMTP_USER = _os.getenv("GMAIL_SMTP_USER", _os.getenv("EMAIL_HOST_USER", ""))
GMAIL_SMTP_PASSWORD = _os.getenv("GMAIL_SMTP_PASSWORD", _os.getenv("EMAIL_HOST_PASSWORD", ""))

# TLS
GMAIL_SMTP_USE_TLS = _os.getenv(
    "GMAIL_SMTP_USE_TLS",
    _os.getenv("EMAIL_USE_TLS", "true"),
).lower() in {"1", "true", "yes"}

# -------------------------
# Web Push (VAPID) Settings
# -------------------------
VAPID_PUBLIC_KEY = _os.getenv("VAPID_PUBLIC_KEY", "BM6l9llDodZefTcQFVHNfe_8q7TRTXkVH9Ipw927BuVLX1t5cgGcH1erFmRZt3SxDqMWp0WP_4e35-96KmBeBeE")
VAPID_PRIVATE_KEY = _os.getenv("VAPID_PRIVATE_KEY", "VO7FZi7XxF3h1BHePn9ecLG7tqiNzfQP1NE64P3gIKY")

TURNSTILE_SITE_KEY = _os.getenv("TURNSTILE_SITE_KEY", "0x4AAAAAAEDmeu1kgCqrkQSI") 
TURNSTILE_SECRET_KEY = _os.getenv("TURNSTILE_SECRET_KEY", "0x4AAAAAAEDmeh_ln6hedjXrv8pLdF869jA") 
TURNSTILE_REQUIRE_ON_LOCALHOST = _os.getenv("TURNSTILE_REQUIRE_ON_LOCALHOST", "false").lower() in {"1", "true", "yes", "on"}


