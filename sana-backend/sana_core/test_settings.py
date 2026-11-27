"""Settings for running Django tests independently of production HTTPS policy.

Load this module with --settings=sana_core.test_settings when running
tests in an environment whose production environment file enables HTTPS
redirects. Production settings remain unchanged.
"""

from .settings import *  # noqa: F403,F401

# Django's test client uses HTTP by default. Production HTTPS enforcement would
# redirect API test requests before the views and DRF throttles are exercised.
SECURE_SSL_REDIRECT = False
