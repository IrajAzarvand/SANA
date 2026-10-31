import os
import unittest
from unittest.mock import patch

from app.config import AppConfig, ConfigurationError


class AppConfigTests(unittest.TestCase):
    def test_loads_database_and_traccar_configuration(self):
        env = {
            "SANA_GPS_DB_NAME": "sana_db",
            "SANA_GPS_DB_USER": "sana_user",
            "SANA_GPS_DB_PASSWORD": "secret",
            "SANA_GPS_TRACCAR_API_URL": "http://127.0.0.1:8082/api/",
            "SANA_GPS_TRACCAR_API_USERNAME": "api-user",
            "SANA_GPS_TRACCAR_API_PASSWORD": "api-password",
            "SANA_GPS_TRACCAR_SYNC_INTERVAL": "75",
            "NESHAN_MAP_MATCHING_API_KEY": "server-only-test-key",
        }
        with patch.dict(os.environ, env, clear=True):
            config = AppConfig.from_env()
        self.assertEqual(config.database.name, "sana_db")
        self.assertEqual(config.database.user, "sana_user")
        self.assertEqual(config.traccar_api_url, "http://127.0.0.1:8082/api")
        self.assertEqual(config.traccar_api_username, "api-user")
        self.assertEqual(config.traccar_sync_interval, 75.0)
        self.assertEqual(config.neshan_map_matching_api_key, "server-only-test-key")

    def test_defaults_to_single_sana_user_database_login(self):
        with patch.dict(os.environ, {"SANA_GPS_DB_NAME": "sana_db"}, clear=True):
            config = AppConfig.from_env()
        self.assertEqual(config.database.user, "sana_user")
        self.assertEqual(config.database.password, "sana_password_123")

    def test_empty_neshan_key_disables_matching(self):
        env = {"SANA_GPS_DB_NAME": "sana_db", "NESHAN_MAP_MATCHING_API_KEY": "   "}
        with patch.dict(os.environ, env, clear=True):
            config = AppConfig.from_env()
        self.assertIsNone(config.neshan_map_matching_api_key)

    def test_rejects_unpaired_traccar_credentials(self):
        env = {"SANA_GPS_DB_NAME": "sana_db", "SANA_GPS_TRACCAR_API_USERNAME": "api-user"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "must be set together"):
                AppConfig.from_env()

    def test_rejects_invalid_database_port(self):
        env = {"SANA_GPS_DB_NAME": "sana_db", "SANA_GPS_DB_PORT": "abc"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "SANA_GPS_DB_PORT must be an integer"):
                AppConfig.from_env()

    def test_rejects_non_finite_traccar_interval(self):
        env = {"SANA_GPS_DB_NAME": "sana_db", "SANA_GPS_TRACCAR_SYNC_INTERVAL": "nan"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "must be a finite number"):
                AppConfig.from_env()

    def test_rejects_invalid_pool_range(self):
        env = {"SANA_GPS_DB_NAME": "sana_db", "SANA_GPS_DB_POOL_MIN": "8", "SANA_GPS_DB_POOL_MAX": "5"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "must not exceed"):
                AppConfig.from_env()

    def test_rejects_non_application_database_role(self):
        env = {"SANA_GPS_DB_NAME": "sana_db", "SANA_GPS_DB_USER": "sana_migrator", "SANA_GPS_DB_PASSWORD": "secret"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "must be 'sana_user'"):
                AppConfig.from_env()


if __name__ == "__main__":
    unittest.main()
