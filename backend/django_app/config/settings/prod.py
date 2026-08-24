from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

SECURE_SSL_REDIRECT = True
# Railway's deploy healthcheck probes the container directly inside its
# own network, bypassing the edge/proxy entirely — so those requests never
# carry X-Forwarded-Proto and would otherwise get a 301 from
# SECURE_SSL_REDIRECT instead of the 200 the healthcheck needs. Real user
# traffic always comes through the edge (which does set that header), so
# this exemption only affects direct-to-container probes.
SECURE_REDIRECT_EXEMPT = [r"^health/?$", r"^api/v1/health/?$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
