import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if present (local development)
load_dotenv(BASE_DIR / '.env')

# ── Security ───────────────────────────────────────────────────────────────────

def _get_bool_env(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def _get_list_env(name, default=''):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development').strip().lower()
IS_PRODUCTION = DJANGO_ENV == 'production'
DEBUG = _get_bool_env('DEBUG', default=not IS_PRODUCTION)

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-dev-only-coconut-wireless'
    else:
        raise ImproperlyConfigured('SECRET_KEY environment variable is required when DEBUG is False.')

ALLOWED_HOSTS = _get_list_env(
    'ALLOWED_HOSTS',
    '127.0.0.1,localhost,testserver' if DEBUG else ''
)
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured('ALLOWED_HOSTS must be set when DEBUG is False.')

CSRF_TRUSTED_ORIGINS = _get_list_env('CSRF_TRUSTED_ORIGINS', '')

# ── Application definition ─────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'marketplace',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'coconut_wireless.urls'

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
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'coconut_wireless.wsgi.application'
ASGI_APPLICATION = 'coconut_wireless.asgi.application'

# ── Database ───────────────────────────────────────────────────────────────────
# Default: SQLite for local development.
# For production set DATABASE_URL in .env or environment, e.g.:
#   DATABASE_URL=postgres://user:pass@host:5432/dbname
# and add dj-database-url + psycopg2 to requirements.txt
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = 'marketplace.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Localisation ───────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Pacific/Fiji'
USE_I18N = True
USE_TZ = True

# ── Static & media files ───────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'   # target for collectstatic in production
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    },
}
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Proxy/HTTPS security defaults ──────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if _get_bool_env('USE_X_FORWARDED_PROTO', False) else None
SESSION_COOKIE_SECURE = _get_bool_env('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = _get_bool_env('CSRF_COOKIE_SECURE', not DEBUG)
SECURE_SSL_REDIRECT = _get_bool_env('SECURE_SSL_REDIRECT', not DEBUG)
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _get_bool_env('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = _get_bool_env('SECURE_HSTS_PRELOAD', False)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Auth redirects ─────────────────────────────────────────────────────────────
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# ── Email ──────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@coconutwireless.fj')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
