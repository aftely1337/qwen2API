import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from backend.api import admin
from backend.core.config import MODEL_MAP, apply_runtime_config, save_runtime_config, settings


ROOT = Path(__file__).resolve().parents[2]
AUTO_REFILL_LABEL = "\u81ea\u52a8\u8865\u53f7\u76ee\u6807\u5065\u5eb7\u8d26\u53f7\u6570"


class AutoRefillTargetSettingTests(unittest.TestCase):
    def setUp(self):
        self.original_config_file = settings.CONFIG_FILE
        self.original_auto_refill_target = settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS
        self.original_max_inflight = settings.MAX_INFLIGHT_PER_ACCOUNT
        self.original_engine_mode = settings.ENGINE_MODE
        self.original_model_map = dict(MODEL_MAP)
        self.tempdir = tempfile.TemporaryDirectory()
        settings.CONFIG_FILE = str(Path(self.tempdir.name) / "config.json")

    def tearDown(self):
        settings.CONFIG_FILE = self.original_config_file
        settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS = self.original_auto_refill_target
        settings.MAX_INFLIGHT_PER_ACCOUNT = self.original_max_inflight
        settings.ENGINE_MODE = self.original_engine_mode
        MODEL_MAP.clear()
        MODEL_MAP.update(self.original_model_map)
        self.tempdir.cleanup()

    def test_runtime_config_helpers_persist_auto_refill_target(self):
        settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS = 7
        save_runtime_config()

        saved = json.loads(Path(settings.CONFIG_FILE).read_text(encoding="utf-8"))
        self.assertEqual(saved["auto_refill_target_min_accounts"], 7)

    def test_apply_runtime_config_updates_auto_refill_target(self):
        settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS = 3

        apply_runtime_config({"auto_refill_target_min_accounts": 9})

        self.assertEqual(settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS, 9)

    def test_admin_settings_payload_exposes_auto_refill_target(self):
        settings.AUTO_REFILL_TARGET_MIN_ACCOUNTS = 6

        payload = asyncio.run(admin.get_settings())

        self.assertEqual(payload["auto_refill_target_min_accounts"], 6)

    def test_frontend_settings_page_contains_auto_refill_setting(self):
        settings_page = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
        main_py = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn("auto_refill_target_min_accounts", settings_page)
        self.assertIn(AUTO_REFILL_LABEL, settings_page)
        self.assertIn("AUTO_REFILL_TARGET_MIN_ACCOUNTS", main_py)
