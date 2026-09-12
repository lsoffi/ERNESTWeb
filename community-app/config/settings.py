import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG: raise RuntimeError("Set DJANGO_SECRET_KEY")
    SECRET_KEY = "local-preview-only-do-not-use-in-production-ernest"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [x for x in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if x]
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.messages", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.staticfiles", "django_otp", "django_otp.plugins.otp_totp", "community"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.locale.LocaleMiddleware", "community.i18n.EmailLanguageMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django_otp.middleware.OTPMiddleware", "community.security.AbuseProtectionMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "community.i18n.context", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
if os.environ.get("MYSQL_HOST"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.mysql", "HOST": os.environ["MYSQL_HOST"], "PORT": os.environ.get("MYSQL_PORT", "3306"), "NAME": os.environ["MYSQL_DATABASE"], "USER": os.environ["MYSQL_USER"], "PASSWORD": os.environ["MYSQL_PASSWORD"], "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'", "ssl_mode": "VERIFY_IDENTITY", "ssl": {"ca": os.environ.get("MYSQL_SSL_CA", str(BASE_DIR / "certs/cern-root-ca.pem"))}}, "CONN_MAX_AGE": 60}}
else:
    if not DEBUG: raise RuntimeError("Production requires MYSQL_HOST and database credentials")
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation." + n} for n in ["UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator"]]
LANGUAGE_CODE = "it"
TIME_ZONE = "Europe/Rome"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
# Enable only behind a proxy that strips client-supplied X-Forwarded-Proto.
if os.environ.get("TRUST_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

PASSWORD_RESET_TIMEOUT = 3600
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'http://127.0.0.1:8771' if DEBUG else '')
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_FILE_PATH = BASE_DIR / 'preview-mails'
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
EMAIL_USE_TLS = not EMAIL_USE_SSL
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'ERNEST Preview <preview@localhost>')
SECURE_REFERRER_POLICY = 'same-origin'

ACCOUNTS_ENABLED = os.environ.get("ACCOUNTS_ENABLED", "1" if DEBUG else "0") == "1"

LANGUAGES = [("it", "Italiano"), ("fr", "Français"), ("en", "English")]

# Set only to proxy addresses/networks documented by the actual CERN route.
# Empty means forwarded client addresses are ignored (conservative shared limits).
TRUSTED_PROXY_CIDRS = [value.strip() for value in os.environ.get('TRUSTED_PROXY_CIDRS', '').split(',') if value.strip()]
import ipaddress
for value in TRUSTED_PROXY_CIDRS:
    if ipaddress.ip_network(value).prefixlen == 0:
        raise RuntimeError('Trusting every address as a proxy is forbidden')
COMMUNITY_MAX_BODY_BYTES = 8192
DATA_UPLOAD_MAX_MEMORY_SIZE = COMMUNITY_MAX_BODY_BYTES
OTP_TOTP_ISSUER = 'ERNEST administration'
OTP_TOTP_THROTTLE_FACTOR = 2
LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'safe': {'()': 'community.safe_logging.SafeFormatter'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'safe'}},
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'community': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
