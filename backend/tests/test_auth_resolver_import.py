import importlib
import unittest


class AuthResolverImportTests(unittest.TestCase):
    def test_auth_resolver_module_imports_without_missing_mail_session(self):
        module = importlib.import_module("backend.services.auth_resolver")
        self.assertTrue(hasattr(module, "activate_account"))
        self.assertTrue(hasattr(module, "AuthResolver"))
