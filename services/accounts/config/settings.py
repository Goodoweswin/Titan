import getpass
import os
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("ACCOUNTS_DEBUG") == "1"
if not DEBUG:
    required = (
        "ACCOUNTS_SECRET_KEY",
        "ACCOUNTS_ISSUER",
        "ACCOUNTS_SESSION_EPOCH",
        "ACCOUNTS_RSA_KEY_FILE",
        "ACCOUNTS_ALLOWED_HOSTS",
        "ACCOUNTS_TRUSTED_PROXY_IPS",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "PGHOST",
        "PGPORT",
        "ACCOUNTS_MAIL_DELIVERY",
        "ACCOUNTS_FROM_EMAIL",
        "ACCOUNTS_SMTP_HOST",
        "ACCOUNTS_SMTP_PORT",
        "ACCOUNTS_SMTP_USER",
        "ACCOUNTS_SMTP_PASSWORD",
    )
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise ImproperlyConfigured("Missing production settings: " + ", ".join(missing))
    if os.environ["ACCOUNTS_MAIL_DELIVERY"] != "smtp":
        raise ImproperlyConfigured("Production requires SMTP delivery")
    if os.environ["PGUSER"] == "postgres":
        raise ImproperlyConfigured(
            "Production requires a dedicated non-superuser database role"
        )
    sender = os.environ["ACCOUNTS_FROM_EMAIL"]
    if "@" not in sender or "." not in sender.rsplit("@", 1)[-1]:
        raise ImproperlyConfigured("Production requires an explicit mail sender")
TRUSTED_PROXY_IPS = []
for peer in filter(None, os.environ.get("ACCOUNTS_TRUSTED_PROXY_IPS", "").split(",")):
    try:
        TRUSTED_PROXY_IPS.append(str(ip_address(peer.strip())))
    except ValueError as exc:
        raise ImproperlyConfigured(
            "Trusted gateways must be exact IP addresses, not networks"
        ) from exc
if not DEBUG and not TRUSTED_PROXY_IPS:
    raise ImproperlyConfigured(
        "Production requires at least one exact trusted gateway IP"
    )
SECRET_KEY = os.environ["ACCOUNTS_SECRET_KEY"]
ISSUER = os.environ["ACCOUNTS_ISSUER"].rstrip("/")
SESSION_EPOCH = os.environ["ACCOUNTS_SESSION_EPOCH"]
if not DEBUG and (not ISSUER.startswith("https://") or len(SECRET_KEY) < 50):
    raise ImproperlyConfigured("Production requires HTTPS issuer and a strong secret")
ALLOWED_HOSTS = os.environ.get(
    "ACCOUNTS_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
).split(",")
if not DEBUG:
    parsed = urlsplit(ISSUER)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ImproperlyConfigured("Production issuer must be an HTTPS origin")
    if ALLOWED_HOSTS != [parsed.hostname]:
        raise ImproperlyConfigured(
            "Allowed hosts must contain only the issuer hostname"
        )
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "oauth2_provider",
    "rest_framework",
    "accounts.apps.AccountsConfig",
]
MIDDLEWARE = [
    "accounts.security.TrustedGatewayMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "accounts.security.BrowserEpochMiddleware",
]
ROOT_URLCONF = "config.urls"
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
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "titan_accounts"),
        "USER": os.environ.get("PGUSER", getpass.getuser()),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "127.0.0.1"),
        "PORT": os.environ.get("PGPORT", "55432"),
        "CONN_MAX_AGE": 0,
    }
}
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
]
LANGUAGE_CODE = "zh-hans"
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
LOGIN_URL = "/login"
SESSION_COOKIE_NAME = "titan_accounts_session"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_NAME = "titan_accounts_csrf"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = [ISSUER]
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# The first middleware strips all forwarded headers and sets the scheme only for
# an exact configured gateway peer. Never enable Django's blanket header trust.
SECURE_REDIRECT_EXEMPT = [r"^health/live$", r"^health/ready$"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("ACCOUNTS_FROM_EMAIL", "accounts@localhost")
OAUTH2_PROVIDER = {
    "OIDC_ENABLED": True,
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
    "COMPLIANT_BCP_RFC9700_REFRESH_TOKEN": True,
    "OIDC_ISS_ENDPOINT": ISSUER,
    "OIDC_RSA_PRIVATE_KEY": Path(os.environ["ACCOUNTS_RSA_KEY_FILE"]).read_text(),
    "OAUTH2_VALIDATOR_CLASS": "accounts.oauth.Validator",
    "SCOPES": {"openid": "Identity", "profile": "Name", "email": "Email"},
    "DEFAULT_SCOPES": ["openid", "profile", "email"],
    "ACCESS_TOKEN_EXPIRE_SECONDS": 600,
    "AUTHORIZATION_CODE_EXPIRE_SECONDS": 60,
    "REFRESH_TOKEN_EXPIRE_SECONDS": 2592000,
    "ROTATE_REFRESH_TOKEN": True,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
    "PKCE_REQUIRED": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
    "OIDC_RESPONSE_TYPES_SUPPORTED": ["code"],
    "OIDC_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED": ["none"],
    "ALLOWED_REDIRECT_URI_SCHEMES": ["http"],
    "OIDC_JWKS_MAX_AGE_SECONDS": 600,
}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}
# Access URLs may contain authorization codes: no request/access logging.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {
        "django.server": {"handlers": ["null"], "propagate": False},
        "django.request": {"handlers": ["null"], "propagate": False},
        "oauthlib": {"handlers": ["null"], "propagate": False},
        "oauth2_provider": {"handlers": ["null"], "propagate": False},
        "django.security": {"handlers": ["null"], "propagate": False},
        "django.db.backends": {"handlers": ["null"], "propagate": False},
    },
}

# RFC 8252 requires HTTP loopback callbacks. Validator permits only exact 127.0.0.1/path.
SILENCED_SYSTEM_CHECKS = ["oauth2_provider.W008"]
DATA_UPLOAD_MAX_MEMORY_SIZE = 16384
DATA_UPLOAD_MAX_NUMBER_FIELDS = 30

ADMIN_ENABLED = os.environ.get("ACCOUNTS_ADMIN_ENABLED") == "1"
EMAIL_TIMEOUT = 10
MAIL_DELIVERY_ENABLED = os.environ.get("ACCOUNTS_MAIL_DELIVERY") == "smtp"
if MAIL_DELIVERY_ENABLED:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["ACCOUNTS_SMTP_HOST"]
    EMAIL_PORT = int(os.environ.get("ACCOUNTS_SMTP_PORT", "587"))
    EMAIL_HOST_USER = os.environ["ACCOUNTS_SMTP_USER"]
    EMAIL_HOST_PASSWORD = os.environ["ACCOUNTS_SMTP_PASSWORD"]
    EMAIL_USE_TLS = True
