import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


HAS_APP_DEPS = importlib.util.find_spec("streamlit") is not None and importlib.util.find_spec("azure") is not None


@unittest.skipUnless(HAS_APP_DEPS, "Install the project's pinned dependencies for Streamlit startup tests")
class AppStartupTests(unittest.TestCase):
    def test_missing_configuration_shows_setup_instead_of_exception(self):
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, {}, clear=True):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=15)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.warning), 1)
        self.assertIn("AZURE_ENDPOINT", app.warning[0].value)
        self.assertIn("OCR belum dijalankan", app.info[0].value)
        self.assertEqual(len(app.get("file_uploader")), 0)

    def test_invalid_endpoint_not_rendered_as_raw_value(self):
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, {"AZURE_ENDPOINT": "http://PRIVATE_TEST_ENDPOINT", "AZURE_KEY": "PRIVATE_TEST_VALUE"}, clear=True):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=15)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.warning), 1)
        self.assertNotIn("PRIVATE_TEST_ENDPOINT", app.warning[0].value)
        self.assertNotIn("PRIVATE_TEST_VALUE", app.warning[0].value)

    def test_configured_startup_does_not_perform_ocr(self):
        from streamlit.testing.v1 import AppTest
        from azure.ai.formrecognizer import DocumentAnalysisClient

        with patch.dict(os.environ, {"AZURE_ENDPOINT": "https://example.cognitiveservices.azure.com/", "AZURE_KEY": "offline-test-value"}, clear=True):
            with patch.object(DocumentAnalysisClient, "begin_analyze_document", side_effect=AssertionError("Startup must not request OCR")) as analyze:
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=15)
            analyze.assert_not_called()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.warning), 0)
        self.assertEqual(len(app.get("file_uploader")), 1)
        self.assertEqual(len(app.success), 0)

    def test_client_initialization_failure_has_no_raw_exception(self):
        from streamlit.testing.v1 import AppTest

        with patch.dict(os.environ, {"AZURE_ENDPOINT": "https://initialization-test.cognitiveservices.azure.com/", "AZURE_KEY": "offline-init-test-value"}, clear=True):
            with patch("azure.ai.formrecognizer.DocumentAnalysisClient", side_effect=ValueError("PRIVATE_CLIENT_ERROR_VALUE")):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=15)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertNotIn("PRIVATE_CLIENT_ERROR_VALUE", app.error[0].value)
        self.assertEqual(len(app.get("file_uploader")), 0)


if __name__ == "__main__":
    unittest.main()
