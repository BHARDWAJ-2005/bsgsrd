"""
Django settings for bsg_sangareddy project.
Bharat Scouts & Guides Enrollment Site for Sangareddy District.
Production-hardened configuration.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env file if present (never committed to git)
_env_path = BASE_DIR / '.env'
if _env_path.exists():
    for _line in _env_path.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if not _line or _line.startswith('#') or '=' not in _line:
            continue
        _k, _v = _line.split('=', 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# ── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY', '_Xzcvapy!ZtjRE2AVQ#sI=52e5t^YM#R6QmyokzJ5dF(VL+BiViYQf(THu(bMt+E')

# Always False in production. Set DJANGO_DEBUG=True only for local dev.
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1')

# Allow all by default; override with comma-separated ALLOWED_HOSTS env var.
_allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = (
    [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()]
    if _allowed_hosts_env != '*' else ['*']
)

# Always allow the official custom domain (no env var needed for this)
_official_domain = 'bsgsrd.indevs.in'
if _official_domain not in ALLOWED_HOSTS and ALLOWED_HOSTS != ['*']:
    ALLOWED_HOSTS.append(_official_domain)

# CSRF: pre-seed common platform domains + official custom domain.
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1',
    'http://localhost',
    'https://*.onrender.com',
    'https://*.railway.app',
    'https://*.pythonanywhere.com',
    # Official production domain
    'https://bsgsrd.indevs.in',
    'http://bsgsrd.indevs.in',
]
_custom_csrf = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if _custom_csrf:
    CSRF_TRUSTED_ORIGINS.extend([c.strip() for c in _custom_csrf.split(',') if c.strip()])

# ── Security headers (active only when DEBUG=False) ─────────────────────────
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    # Render/Railway terminate SSL at the load balancer; trust their forwarded proto
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = False      # LB already handles redirect; avoid double-redirect
    SECURE_HSTS_SECONDS = 0          # Disable HSTS — Render controls HTTPS at the edge

SILENCED_SYSTEM_CHECKS = ['security.W004', 'security.W008']

# Session expires after 8 hours of inactivity (school working day)
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True

# ── Apps ────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # cloudinary_storage and cloudinary are added ONLY when keys are set
    # (see the Cloudinary config block below — it appends to INSTALLED_APPS).
    'enrollment.apps.EnrollmentConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bsg_sangareddy.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'enrollment.context_processors.bsg_global_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'bsg_sangareddy.wsgi.application'

# ── Database ────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if DATABASE_URL:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            # Do NOT pass ssl_require=True — Neon URL already contains
            # sslmode=require&channel_binding=require; double-applying SSL
            # causes a psycopg2 "conflicting options" error at startup.
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 20,
            }
        }
    }

# ── Password validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
]

# ── i18n / timezone ──────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ── Static files ─────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ── Media & Cloud Storage (Cloudinary if configured, else local media/) ──────
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '').strip()
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '').strip()
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '').strip()
CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL', '').strip()

if CLOUDINARY_URL and not (CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET):
    # Parse cloudinary://api_key:api_secret@cloud_name so django-cloudinary-storage has all keys
    from urllib.parse import urlparse
    _parsed = urlparse(CLOUDINARY_URL)
    if _parsed.scheme == 'cloudinary':
        CLOUDINARY_API_KEY = _parsed.username or ''
        CLOUDINARY_API_SECRET = _parsed.password or ''
        CLOUDINARY_CLOUD_NAME = _parsed.hostname or ''

USE_CLOUDINARY = bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)

if USE_CLOUDINARY:
    # Only register cloudinary apps when keys are present — importing
    # cloudinary_storage without CLOUDINARY_STORAGE configured causes a
    # startup crash (ImproperlyConfigured) which produces Internal Server Error.
    INSTALLED_APPS.insert(INSTALLED_APPS.index('enrollment.apps.EnrollmentConfig'), 'cloudinary_storage')
    INSTALLED_APPS.insert(INSTALLED_APPS.index('enrollment.apps.EnrollmentConfig'), 'cloudinary')
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': CLOUDINARY_API_KEY,
        'API_SECRET': CLOUDINARY_API_SECRET,
    }
    _DEFAULT_MEDIA_BACKEND = 'cloudinary_storage.storage.MediaCloudinaryStorage'
else:
    _DEFAULT_MEDIA_BACKEND = 'django.core.files.storage.FileSystemStorage'

STORAGES = {
    "default": {
        "BACKEND": _DEFAULT_MEDIA_BACKEND,
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Auth URLs ────────────────────────────────────────────────────────────────
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# ── SQLite WAL for concurrent writes ─────────────────────────────────────────
SQLITE_WAL_MODE = True

# ── Logging (production errors to console for Render/Railway log capture) ────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'enrollment': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
