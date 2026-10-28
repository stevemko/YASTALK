"""
Django settings for yastalk project.
"""

from datetime import timedelta
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

# Move the admin login away from the guessable /admin/ (set ADMIN_URL=my-secret-path/)
ADMIN_URL = config('ADMIN_URL', default='admin/').strip('/') + '/'

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='yas-talk.onrender.com,localhost,127.0.0.1',
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
    'rest_framework_simplejwt.token_blacklist',     # lets logout revoke refresh tokens
    'corsheaders',

    # local
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',          # high in the list
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.gzip.GZipMiddleware',
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
        conn_max_age=600,
        conn_health_checks=True,
    )
}
DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True


# ---------------------------------------------------------------------------
# Cache
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
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},
    },
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
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'login': '10/minute',
        'register': '5/minute',
        'password_reset': '5/hour',
        'verify': '30/hour',
        'verify_resend': '5/hour',
        'change_password': '10/hour',
    },
}
# Only set this once you are sure how many proxies sit in front of Django.
# A wrong number makes every visitor look like the same IP. Leave unset if unsure:
# the per-email login lockout protects accounts either way.
_NUM_PROXIES = config('NUM_PROXIES', default='')
if _NUM_PROXIES:
    REST_FRAMEWORK['NUM_PROXIES'] = int(_NUM_PROXIES)
if not DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = ['rest_framework.renderers.JSONRenderer']


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}


# ---------------------------------------------------------------------------
# Password reset links
# ---------------------------------------------------------------------------
FRONTEND_URL = config('FRONTEND_URL', default='https://yas-talk.vercel.app')
PASSWORD_RESET_TIMEOUT = 3600


# ---------------------------------------------------------------------------
# CORS / CSRF
# ---------------------------------------------------------------------------
_FRONTEND_ORIGINS = (
    'https://yas-talk-50hg0pris-greenlightled.vercel.app,'
    'https://yas-talk.vercel.app,'
    'http://localhost:5173,'
    'http://127.0.0.1:5173,'
    'http://localhost:5176,'
    'http://127.0.0.1:5176'
)
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default=_FRONTEND_ORIGINS, cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default=_FRONTEND_ORIGINS, cast=Csv())

CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https://yas-talk-[a-z0-9]+-greenlightled\.vercel\.app$',
]

# Allow all origins while developing (removes CORS headaches locally)
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True


# ---------------------------------------------------------------------------
# Production security
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SECURE_REDIRECT_EXEMPT = [r'^api/health/$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config('HSTS_SECONDS', default=31536000, cast=int)   # 1 year
    SECURE_CONTENT_TYPE_NOSNIFF = True


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
# Render's free tier blocks SMTP ports (25/465/587), so on the live site mail
# goes out through Brevo's HTTPS API instead. Set BREVO_API_KEY to turn it on.
#   BREVO_API_KEY  -> Brevo API (use this on Render)
#   EMAIL_HOST_USER -> classic SMTP (works locally, NOT on Render free)
#   neither        -> emails are printed in the terminal (handy in development)
BREVO_API_KEY = config('BREVO_API_KEY', default='')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_TIMEOUT = 10

if BREVO_API_KEY:
    INSTALLED_APPS += ['anymail']
    EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'
    ANYMAIL = {'BREVO_API_KEY': BREVO_API_KEY, 'REQUESTS_TIMEOUT': (5, 15)}
elif EMAIL_HOST_USER:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    if not DEBUG:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            'No email provider configured: password-reset and verification emails '
            'will NOT be delivered. Set BREVO_API_KEY.'
        )

# Must be a sender you have verified in Brevo (Senders & IP), e.g.
#   DEFAULT_FROM_EMAIL=YasTalk <you@yourdomain.com>
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER or 'noreply@yastalk.com')

# How long an email-verification link stays valid
EMAIL_VERIFY_MAX_AGE = 3 * 24 * 3600   # 3 days


# ---------------------------------------------------------------------------
# App links
# ---------------------------------------------------------------------------
APP_LINKS = {
    'web_app': config('APP_WEB_URL', default=''),
    'android': config('APP_ANDROID_URL', default=''),
    'ios': config('APP_IOS_URL', default=''),
    'waitlist': config('APP_WAITLIST_URL', default=''),
}


# ---------------------------------------------------------------------------
# Logging
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