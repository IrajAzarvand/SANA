import os
import unittest
from unittest.mock import patch

from app.config import AppConfig, ConfigurationError


class AppConfigTests(unittest.TestCase):
    def test_loads_transport_configuration_from_environment(self):
        env = {
            "SANA_GPS_TCP_PORT": "9100",
            "SANA_GPS_UDP_PORT": "9101",
            "SANA_GPS_DB_NAME": "sana_db",
            "SANA_GPS_DB_USER": "sana_user",
            "SANA_GPS_DB_PASSWORD": "secret",
        }

        with patch.dict(os.environ, env, clear=False):
            config = AppConfig.from_env()

        self.assertEqual(config.tcp_port, 9100)
        self.assertEqual(config.udp_port, 9101)

    def test_loads_transport_limits_from_environment(self):
        env = {
            "SANA_GPS_TCP_IDLE_TIMEOUT": "12.5",
            "SANA_GPS_UDP_SESSION_TIMEOUT": "20",
            "SANA_GPS_MAX_TCP_CONNECTIONS": "3",
            "SANA_GPS_MAX_UDP_SESSIONS": "50",
            "SANA_GPS_MAX_DATAGRAM_SIZE": "4096",
            "SANA_GPS_DB_NAME": "sana_db",
            "SANA_GPS_DB_USER": "sana_user",
            "SANA_GPS_DB_PASSWORD": "secret",
        }
        with patch.dict(os.environ, env, clear=False):
            config = AppConfig.from_env()
        self.assertEqual(config.tcp_idle_timeout, 12.5)
        self.assertEqual(config.udp_session_timeout, 20.0)
        self.assertEqual(config.max_tcp_connections, 3)
        self.assertEqual(config.max_udp_sessions, 50)
        self.assertEqual(config.max_datagram_size, 4096)

    def test_loads_database_configuration_from_environment(self):
        env = {
            "SANA_GPS_DB_NAME": "sana_db",
            "SANA_GPS_DB_USER": "sana_user",
            "SANA_GPS_DB_PASSWORD": "secret",
            "SANA_GPS_DB_POOL_MIN": "2",
            "SANA_GPS_DB_POOL_MAX": "7",
        }

        with patch.dict(os.environ, env, clear=False):
            config = AppConfig.from_env()

        self.assertEqual(config.database.name, "sana_db")
        self.assertEqual(config.database.user, "sana_user")
        self.assertEqual(config.database.pool_min_size, 2)
        self.assertEqual(config.database.pool_max_size, 7)

    def test_rejects_non_integer_database_port(self):
        env = {
            "SANA_GPS_DB_NAME": "sana_db",
            "SANA_GPS_DB_USER": "sana_user",
            "SANA_GPS_DB_PASSWORD": "secret",
            "SANA_GPS_DB_PORT": "abc",
        }

        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(
                ConfigurationError, "SANA_GPS_DB_PORT must be an integer"
            ):
                AppConfig.from_env()

    def test_rejects_non_finite_timeout(self):
        env = {
            "SANA_GPS_DB_NAME": "sana_db",
            "SANA_GPS_DB_USER": "sana_user",
            "SANA_GPS_DB_PASSWORD": "secret",
            "SANA_GPS_TCP_IDLE_TIMEOUT": "nan",
        }

        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(
                ConfigurationError, "SANA_GPS_TCP_IDLE_TIMEOUT must be a finite number"
            ):
                AppConfig.from_env()

    def test_rejects_invalid_pool_range(self):
        env = {
            "SANA_GPS_DB_NAME": "sana_db",
            "SANA_GPS_DB_USER": "sana_user",
            "SANA_GPS_DB_PASSWORD": "secret",
            "SANA_GPS_DB_POOL_MIN": "8",
            "SANA_GPS_DB_POOL_MAX": "5",
        }

        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(
                ConfigurationError, "SANA_GPS_DB_POOL_MIN must not exceed"
            ):
                AppConfig.from_env()


if __name__ == "__main__":
    unittest.main()
