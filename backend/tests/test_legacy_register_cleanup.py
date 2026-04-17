from pathlib import Path
import unittest

from backend.api.admin import router
from backend.core.config import Settings


ROOT = Path(__file__).resolve().parents[2]


class LegacyRegisterCleanupTests(unittest.TestCase):
    def test_legacy_register_routes_are_removed(self):
        paths = {route.path for route in router.routes}

        self.assertNotIn("/accounts/register", paths)
        self.assertNotIn("/accounts/register-verify", paths)

    def test_register_secret_setting_is_removed(self):
        model_fields = getattr(Settings, "model_fields", {})
        self.assertNotIn("REGISTER_SECRET", model_fields)

    def test_accounts_page_no_longer_contains_legacy_one_click_register_flow(self):
        accounts_page = (ROOT / "frontend" / "src" / "pages" / "AccountsPage.tsx").read_text(encoding="utf-8")

        self.assertNotIn("registerUnlocked", accounts_page)
        self.assertNotIn("handleAutoRegister", accounts_page)
        self.assertNotIn("/api/admin/accounts/register", accounts_page)
        self.assertNotIn("一键获取新号", accounts_page)

    def test_readme_no_longer_mentions_register_secret(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("REGISTER_SECRET", readme)
