from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key")
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
allowed_hosts_env = os.environ.get("ALLOWED_HOSTS")

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
if render_host:
    ALLOWED_HOSTS.append(render_host)
if allowed_hosts_env:
    ALLOWED_HOSTS += [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = []
if render_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_host}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "axes",
    "core.apps.CoreConfig",
    "push.apps.PushConfig",
    "panel_settings.apps.PanelSettingsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Axes backend primero (anti brute force)
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

ROOT_URLCONF = "invpanel.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "core.context_processors.nav_badges",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "invpanel.wsgi.application"
ASGI_APPLICATION = "invpanel.asgi.application"

DB_URL = os.environ.get("DATABASE_URL", "").strip()

# Database selection:
# - If DATABASE_URL points to Postgres => use Postgres (recommended for production/persistence)
# - If DATABASE_URL points to sqlite:///... => use that sqlite file
# - Else => local sqlite db.sqlite3 (safe default for dev)
if DB_URL.startswith("sqlite"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DB_URL.replace("sqlite:///", ""),
        }
    }
elif DB_URL.startswith(("postgres://", "postgresql://")):
    # Render Postgres usually requires SSL. dj-database-url will set the correct engine.
    DATABASES = {"default": dj_database_url.parse(DB_URL, conn_max_age=600, ssl_require=not DEBUG)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Fallback for PaaS environments where collectstatic isn't executed as expected
WHITENOISE_USE_FINDERS = True
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/login/"
LOGOUT_REDIRECT_URL = "/login/"

# Cookies / Session hardening
SESSION_COOKIE_SECURE = bool(render_host)
CSRF_COOKIE_SECURE = bool(render_host)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_SSL_REDIRECT = bool(render_host) and not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30 if render_host else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

# django-axes (anti brute force)
AXES_FAILURE_LIMIT = int(os.environ.get("AXES_FAILURE_LIMIT", "5"))
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCK_OUT_AT_FAILURE = True
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
# ----------------------------
# Email (alertas)
# ----------------------------
# En desarrollo local podés usar console backend para ver los mails en logs.
# En Render, configurá SMTP por variables de entorno.

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1").lower() in ("1", "true", "yes")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@invpanel-pro")

# Email destino de alertas (si no se define, cae a ADMIN_EMAIL)
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "")


# --- IA (OpenAI API) ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

# Gobernanza IA (por defecto activada si hay API key)
AI_GOVERNANCE_REQUIRED = os.environ.get("AI_GOVERNANCE_REQUIRED", "1").strip() not in ("0","false","False","no","NO")
AI_MIN_SCORE = int(os.environ.get("AI_MIN_SCORE", "70"))
AI_ALLOW_MANUAL_OVERRIDE = os.environ.get("AI_ALLOW_MANUAL_OVERRIDE", "0").strip() in ("1","true","True","yes","YES")
AI_MAX_EVAL_PER_CLICK = int(os.environ.get("AI_MAX_EVAL_PER_CLICK", "5"))

