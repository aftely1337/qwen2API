from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]

MANAGE_KEY = "\u7ba1\u7406 Key"
ADMIN_KEY_LABEL = "\u7ba1\u7406\u53f0 Key"
SESSION_KEY = "\u4f1a\u8bdd Key"
CURRENT_SESSION_KEY = "\u5f53\u524d\u4f1a\u8bdd Key"
RESET_DEFAULT = "\u6062\u590d\u9ed8\u8ba4 admin"


class FrontendAdminKeyRecoveryTests(unittest.TestCase):
    def test_auth_helper_normalizes_bearer_prefix(self):
        auth_ts = (ROOT / "frontend" / "src" / "lib" / "auth.ts").read_text(encoding="utf-8")

        self.assertIn("normalizeAdminKeyInput", auth_ts)
        self.assertIn('replace(/^Bearer\\s+/i, "")', auth_ts)

    def test_layout_exposes_global_admin_key_entrypoint(self):
        layout = (ROOT / "frontend" / "src" / "layouts" / "AdminLayout.tsx").read_text(encoding="utf-8")

        self.assertIn(MANAGE_KEY, layout)
        self.assertIn(RESET_DEFAULT, layout)

    def test_settings_page_uses_admin_key_wording_instead_of_session_key(self):
        settings_page = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")

        self.assertIn(ADMIN_KEY_LABEL, settings_page)
        self.assertNotIn(SESSION_KEY, settings_page)
        self.assertNotIn(CURRENT_SESSION_KEY, settings_page)

    def test_frontend_error_messages_reference_admin_key_recovery(self):
        dashboard = (ROOT / "frontend" / "src" / "pages" / "Dashboard.tsx").read_text(encoding="utf-8")
        tokens = (ROOT / "frontend" / "src" / "pages" / "TokensPage.tsx").read_text(encoding="utf-8")

        self.assertIn(MANAGE_KEY, dashboard)
        self.assertIn(MANAGE_KEY, tokens)
        self.assertNotIn(SESSION_KEY, dashboard)
        self.assertNotIn(SESSION_KEY, tokens)
