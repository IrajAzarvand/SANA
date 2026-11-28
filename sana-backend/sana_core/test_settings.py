"""Settings for running Django tests independently of production HTTPS policy.

Load this module with --settings=sana_core.test_settings when running
tests in an environment whose production environment file enables HTTPS
redirects. Production settings remain unchanged.
"""

from .settings import *  # noqa: F403,F401

# Django's test client uses HTTP by default. Production HTTPS enforcement would
# redirect API test requests before the views and DRF throttles are exercised.
SECURE_SSL_REDIRECT = False

# Password hashing is intentionally expensive in production. The test suite
# creates many disposable users, so use Django's fast test-only hasher to avoid
# spending most of the suite runtime on PBKDF2. This setting is isolated to
# this module and does not affect production settings or stored passwords.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
