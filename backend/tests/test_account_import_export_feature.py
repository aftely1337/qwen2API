from pathlib import Path
import unittest

from backend.api import admin
from backend.core.account_pool import Account


ROOT = Path(__file__).resolve().parents[2]

EXPORT_LABEL = "\u5bfc\u51fa\u8d26\u53f7"
IMPORT_LABEL = "\u5bfc\u5165\u8d26\u53f7"


class AccountImportExportFeatureTests(unittest.TestCase):
    def test_admin_routes_expose_account_import_export(self):
        paths = {route.path for route in admin.router.routes}

        self.assertIn("/accounts/export", paths)
        self.assertIn("/accounts/import", paths)

    def test_build_account_export_payload_contains_metadata_and_accounts(self):
        payload = admin.build_account_export_payload([
            Account(email="demo@example.com", token="tok-1", password="pw-1", username="Demo"),
        ])

        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["count"], 1)
        self.assertIn("exported_at", payload)
        self.assertEqual(payload["accounts"][0]["email"], "demo@example.com")
        self.assertEqual(payload["accounts"][0]["token"], "tok-1")

    def test_parse_account_import_payload_accepts_export_envelope_and_deduplicates(self):
        parsed = admin.parse_account_import_payload({
            "accounts": [
                {"email": "demo@example.com", "token": "tok-1", "password": "pw-1"},
                {"email": "demo@example.com", "token": "tok-2", "password": "pw-2", "username": "Updated"},
            ]
        })

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].email, "demo@example.com")
        self.assertEqual(parsed[0].token, "tok-2")
        self.assertEqual(parsed[0].password, "pw-2")
        self.assertEqual(parsed[0].username, "Updated")

    def test_parse_account_import_payload_rejects_missing_accounts(self):
        with self.assertRaises(ValueError):
            admin.parse_account_import_payload({"accounts": [{"email": "missing-token@example.com"}]})

    def test_accounts_page_contains_import_export_controls(self):
        accounts_page = (ROOT / "frontend" / "src" / "pages" / "AccountsPage.tsx").read_text(encoding="utf-8")

        self.assertIn("/api/admin/accounts/export", accounts_page)
        self.assertIn("/api/admin/accounts/import", accounts_page)
        self.assertIn(EXPORT_LABEL, accounts_page)
        self.assertIn(IMPORT_LABEL, accounts_page)
        self.assertIn('type="file"', accounts_page)
