import hashlib
import sys
import types
import unittest
from unittest.mock import patch

if "pydantic_settings" not in sys.modules:
    pydantic_settings = types.ModuleType("pydantic_settings")

    class _BaseSettings:
        def __init__(self, *args, **kwargs):
            pass

    pydantic_settings.BaseSettings = _BaseSettings
    sys.modules["pydantic_settings"] = pydantic_settings

from backend.services.auto_registrar import QwenAutoRegistrar
from backend.services.account_health import count_healthy_accounts
from backend.services.tempmail_client import TempMailClient


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeHttpClient:
    def __init__(self):
        self.calls = []
        self._post_response = _FakeResponse({})
        self._get_response = _FakeResponse({})

    async def post(self, url, json=None, headers=None):
        self.calls.append(("POST", url, json, headers))
        return self._post_response

    async def get(self, url, headers=None):
        self.calls.append(("GET", url, None, headers))
        return self._get_response


class TempMailClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_email_uses_v2_inbox_create_endpoint(self):
        client = TempMailClient()
        fake_http = _FakeHttpClient()
        fake_http._post_response = _FakeResponse(
            {"address": "demo@example.com", "token": "temp-token"},
            status_code=201,
        )
        client.client = fake_http

        inbox = await client.generate_email()

        self.assertEqual(inbox, {"address": "demo@example.com", "token": "temp-token"})
        self.assertEqual(fake_http.calls[0][0], "POST")
        self.assertEqual(fake_http.calls[0][1], "https://api.tempmail.lol/v2/inbox/create")

    async def test_check_inbox_uses_v2_inbox_token_query(self):
        client = TempMailClient()
        fake_http = _FakeHttpClient()
        fake_http._get_response = _FakeResponse(
            {"emails": [{"subject": "hello"}], "expired": False},
            status_code=200,
        )
        client.client = fake_http

        emails = await client.check_inbox("mail-token")

        self.assertEqual(emails, [{"subject": "hello"}])
        self.assertEqual(fake_http.calls[0][0], "GET")
        self.assertEqual(fake_http.calls[0][1], "https://api.tempmail.lol/v2/inbox?token=mail-token")


class AutoRegistrarHelperTests(unittest.TestCase):
    def test_build_signup_payload_hashes_password_and_sets_defaults(self):
        registrar = QwenAutoRegistrar()

        payload = registrar._build_signup_payload(
            email="demo@example.com",
            password="Secret123!A",
            name="Demo User",
        )

        self.assertEqual(payload["email"], "demo@example.com")
        self.assertEqual(payload["name"], "Demo User")
        self.assertEqual(
            payload["password"],
            hashlib.sha256("Secret123!A".encode("utf-8")).hexdigest(),
        )
        self.assertTrue(payload["agree"])
        self.assertEqual(payload["module"], "chat")
        self.assertIn("profile_image_url", payload)

    def test_extract_activation_link_prefers_qwen_activation_url(self):
        registrar = QwenAutoRegistrar()
        activation_link = (
            "https://chat.qwen.ai/api/v1/auths/activate"
            "?id=abc123&token=def456"
        )
        email_data = {
            "subject": "qwen.ai active mail.",
            "html": f'<a href="{activation_link}">Activate account</a>',
            "body": "[email has empty or invalid body]",
        }

        link = registrar._extract_activation_link(email_data)

        self.assertEqual(link, activation_link)


class AutoRegistrarFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_activate_account_uses_allow_redirects_with_curl_cffi(self):
        registrar = QwenAutoRegistrar()
        captured = {}

        class _FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, headers=None, allow_redirects=None):
                captured["url"] = url
                captured["allow_redirects"] = allow_redirects
                captured["headers"] = headers or {}

                class _Response:
                    status_code = 200
                    text = "ok"

                return _Response()

        with patch("backend.services.auto_registrar.AsyncSession", return_value=_FakeClient()):
            await registrar._activate_account("https://chat.qwen.ai/api/v1/auths/activate?id=1&token=2")

        self.assertEqual(captured["url"], "https://chat.qwen.ai/api/v1/auths/activate?id=1&token=2")
        self.assertTrue(captured["allow_redirects"])


class AccountHealthTests(unittest.TestCase):
    def test_count_healthy_accounts_uses_status_code_semantics(self):
        class _FakeAccount:
            def __init__(self, status_code, rate_limited=False):
                self._status_code = status_code
                self._rate_limited = rate_limited

            def get_status_code(self):
                return self._status_code

            def is_rate_limited(self):
                return self._rate_limited

        accounts = [
            _FakeAccount("valid"),
            _FakeAccount("valid", rate_limited=True),
            _FakeAccount("pending_activation"),
            _FakeAccount("auth_error"),
        ]

        self.assertEqual(count_healthy_accounts(accounts), 1)
