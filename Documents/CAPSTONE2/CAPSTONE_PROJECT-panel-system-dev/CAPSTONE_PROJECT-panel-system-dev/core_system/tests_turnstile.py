from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core_system.turnstile import is_turnstile_enabled, validate_turnstile_token


class TurnstileSecurityTests(SimpleTestCase):
    @override_settings(TURNSTILE_SITE_KEY="", TURNSTILE_SECRET_KEY="")
    def test_turnstile_is_disabled_when_not_configured(self):
        self.assertFalse(is_turnstile_enabled())

    def test_validation_returns_false_for_missing_token(self):
        self.assertFalse(validate_turnstile_token(""))

    @override_settings(TURNSTILE_SITE_KEY="site-key", TURNSTILE_SECRET_KEY="secret-key", TURNSTILE_REQUIRE_ON_LOCALHOST=False)
    def test_localhost_bypasses_turnstile_by_default(self):
        request = SimpleNamespace(get_host=lambda: "localhost:8000")
        self.assertFalse(is_turnstile_enabled(request))

    @override_settings(TURNSTILE_SITE_KEY="site-key", TURNSTILE_SECRET_KEY="secret-key")
    @patch("core_system.turnstile._post_turnstile_siteverify")
    def test_validation_accepts_successful_cloudflare_response(self, mock_post):
        mock_post.return_value = {"success": True}

        self.assertTrue(validate_turnstile_token("token-123", remote_ip="127.0.0.1"))
        mock_post.assert_called_once()
