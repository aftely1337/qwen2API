from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ImageEditPageRouteTests(unittest.TestCase):
    def test_app_registers_image_edit_route(self):
        app_tsx = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")

        self.assertIn('path="images/edit"', app_tsx)
        self.assertIn('ImageEditPage', app_tsx)

    def test_image_edit_page_calls_openai_edits_endpoint(self):
        page = (ROOT / "frontend" / "src" / "pages" / "ImageEditPage.tsx").read_text(encoding="utf-8")

        self.assertIn("/v1/images/edits", page)
        self.assertIn("图像编辑", page)

    def test_image_edit_page_no_longer_offers_ratio_selector(self):
        page = (ROOT / "frontend" / "src" / "pages" / "ImageEditPage.tsx").read_text(encoding="utf-8")

        self.assertIn("默认继承原图比例", page)
        self.assertNotIn("输出尺寸", page)
        self.assertNotIn('formData.append("size"', page)
