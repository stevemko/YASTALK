"""
Django settings for yastalk project.
"""

from pathlib import Path

import dj_database_url
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
_INSECURE_KEY = 'django-insecure-CHANGE-ME-IN-PRODUCTION'
SECRET_KEY = config('DJANGO_SECRET_KEY', default=_INSECURE_KEY)

# Defaults to False (safe). Set DEBUG=True in your local .env for development.
DEBUG = config('DEBUG', default=False, cast=bool)

if not DEBUG and SECRET_KEY == _INSECURE_KEY:
    raise ImproperlyConfigured('Set DJANGO_SECRET_KEY in the environment for production.')

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='yastalk.onrender.com,localhost,127.0.0.1',
    cast=Csv(),
)
_render_host = config('RENDER_EXTERNAL_HOSTNAME', default='')   # set automatically by Render
if _render_host and _render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_render_host)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # third-party
    'rest_framework',
    'corsheaders',

    # local
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.gzip.GZipMiddleware',            # compress API JSON responses
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'yastalk.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'yastalk.wsgi.application'


# ---------------------------------------------------------------------------
# Database: Neon PostgreSQL in production, SQLite locally
# ---------------------------------------------------------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,           # reuse connections instead of reconnecting every request
        conn_health_checks=True,    # drop stale connections (Neon sleeps idle databases)
    )
}
# Needed when using Neon's pooled (pgbouncer) connection string
DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True


# ---------------------------------------------------------------------------
# Cache (used for the M-Pesa token and cached public endpoints)
# ---------------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'yastalk-cache',
    }
}


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Uploaded images (e.g. TeamMember.photo) must live on Cloudinary in production,
# because Render's disk is wiped on every deploy. Active only when CLOUDINARY_URL is set.
CLOUDINARY_URL = config('CLOUDINARY_URL', default='')
if CLOUDINARY_URL:
    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']
    CLOUDINARY_STORAGE = {'CLOUDINARY_URL': CLOUDINARY_URL}
    STORAGES['default'] = {'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage'}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ---------------------------------------------------------------------------
# REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # raised from 30 so payment-status polling (every 3s) + page loads don't get blocked
        'anon': '60/minute',
    },
}
if not DEBUG:
    # JSON only in production: skips the browsable-API HTML renderer
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = ['rest_framework.renderers.JSONRenderer']


# ---------------------------------------------------------------------------
# CORS / CSRF (React dev server + production frontend on Vercel)
# ---------------------------------------------------------------------------
_FRONTEND_ORIGINS = (
    'https://yas-talk-50hg0pris-greenlightled.vercel.app,'
    'https://yas-talk.vercel.app,'
    'http://localhost:5173,'
    'http://127.0.0.1:5173'
)
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default=_FRONTEND_ORIGINS, cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default=_FRONTEND_ORIGINS, cast=Csv())

# Vercel preview deployments get a new URL each time (yas-talk-<hash>-greenlightled.vercel.app)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https://yas-talk-[a-z0-9]+-greenlightled\.vercel\.app$',
]


# ---------------------------------------------------------------------------
# Production security (Render terminates HTTPS in front of Django)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SECURE_REDIRECT_EXEMPT = [r'^api/health/$']     # so uptime pings never get redirected
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600      # start low; raise to 31536000 once everything works
    SECURE_CONTENT_TYPE_NOSNIFF = True


# ---------------------------------------------------------------------------
# Email (contact form / payment confirmations)
# ---------------------------------------------------------------------------
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')   # Gmail: use an App Password
EMAIL_TIMEOUT = 10      # never let a slow mail server hang a worker
EMAIL_BACKEND = (
    'django.core.mail.backends.smtp.EmailBackend'
    if EMAIL_HOST_USER
    else 'django.core.mail.backends.console.EmailBackend'
)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER or 'noreply@yastalk.com')


# ---------------------------------------------------------------------------
# Direct links to the app being built (served by /api/app-links/)
# Empty values are hidden; fill them in on Render when each link exists.
# ---------------------------------------------------------------------------
APP_LINKS = {
    'web_app': config('APP_WEB_URL', default=''),
    'android': config('APP_ANDROID_URL', default=''),
    'ios': config('APP_IOS_URL', default=''),
    'waitlist': config('APP_WAITLIST_URL', default=''),
}


# ---------------------------------------------------------------------------
# Logging: errors and payment events show up in Render's log stream
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '%(levelname)s %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'core': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}