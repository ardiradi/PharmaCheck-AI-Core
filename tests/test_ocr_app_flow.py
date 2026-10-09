import importlib.util
from io import BytesIO
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


HAS_APP_DEPS = importlib.util.find_spec("streamlit") is not None and importlib.util.find_spec("azure") is not None


@unittest.skipUnless(HAS_APP_DEPS, "Install pinned dependencies for offline OCR workflow tests")
class OcrAppFlowTests(unittest.TestCase):
    def exercise_failure(self, error, fixture_name):
        from PIL import Image
        import streamlit as st
        from streamlit.proto.Common_pb2 import FileURLs
        from streamlit.runtime.uploaded_file_manager import UploadedFile, UploadedFileRec
        from streamlit.testing.v1 import AppTest

        buffer = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(buffer, format="PNG")
        contents = buffer.getvalue()
        real_uploader = st.file_uploader

        def offline_upload(*args, **kwargs):
            # Render the real widget, but inject a local file without HTTP upload.
            real_uploader(*args, **kwargs)
            return UploadedFile(UploadedFileRec("offline-image", "offline.png", "image/png", contents), FileURLs())

        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        client = Mock()
        client.begin_analyze_document.return_value.result.side_effect = error
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
        app.secrets = {"offline_fixture": True}
        with patch.dict(os.environ, {
            "AZURE_ENDPOINT": f"https://{fixture_name}.cognitiveservices.azure.com/",
            "AZURE_KEY": "PRIVATE_FIXTURE_KEY",
        }, clear=False), \
            patch("azure.ai.formrecognizer.DocumentAnalysisClient", return_value=client), \
            patch("streamlit.file_uploader", side_effect=offline_upload), \
            patch("streamlit.config.get_config_files", return_value=[]), \
            patch("streamlit.runtime.secrets.Secrets._parse_file_path", side_effect=AssertionError("Do not read real secrets")) as secret_read, \
            patch("socket.socket.connect", side_effect=AssertionError("Do not access the network")) as connect:
            app.run(timeout=15)
            app.radio[0].set_value("Azure (opsional)").run(timeout=15)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.get("imgs")), 1)
            self.assertEqual(len(app.get("file_uploader")), 1)
            self.assertEqual(len(app.warning), 0)
            client.begin_analyze_document.assert_not_called()
            with self.assertLogs("pharmacheck.ocr", level="ERROR") as captured:
                app.button[0].click().run(timeout=15)
            secret_read.assert_not_called()
            connect.assert_not_called()

        client.begin_analyze_document.assert_called_once_with("prebuilt-document", document=contents)
        client.begin_analyze_document.return_value.result.assert_called_once_with()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(len(app.success), 0)
        self.assertEqual(len(app.warning), 0)
        self.assertEqual(len(app.get("imgs")), 1)
        self.assertEqual(len(captured.records), 1)
        self.assertFalse(captured.records[0].exc_info)
        self.assertIsNone(captured.records[0].stack_info)
        self.assertNotIn("PRIVATE", app.error[0].value)
        self.assertNotIn("PRIVATE", captured.output[0])
        self.assertNotIn("cognitiveservices", captured.output[0])
        for kind in ("title", "header", "subheader", "markdown", "caption", "text", "info", "warning", "error", "success"):
            for element in app.get(kind):
                value = getattr(element, "value", "")
                if isinstance(value, str):
                    self.assertNotIn("PRIVATE", value)
        if error.response is not None:
            error.response.text.assert_not_called()
        return app, captured.records[0].getMessage()

    def test_known_provider_failure_has_safe_ui_and_single_call(self):
        from azure.core.exceptions import HttpResponseError

        error = HttpResponseError(message="PRIVATE_MESSAGE https://PRIVATE_ENDPOINT/?key=PRIVATE_KEY")
        error.status_code = 403
        error.error = SimpleNamespace(code="Forbidden", message="PRIVATE_DOCUMENT")
        error.response = SimpleNamespace(status_code=403, headers={"PRIVATE_HEADER": "PRIVATE_KEY"}, body="PRIVATE_DOCUMENT", request=SimpleNamespace(url="https://PRIVATE_ENDPOINT/?key=PRIVATE_KEY"), text=Mock(side_effect=AssertionError("Do not read provider body")))
        app, log = self.exercise_failure(error, "known-offline-error")
        self.assertIn("aturan akses", app.error[0].value)
        self.assertEqual(log, "OCR failed: exception_type=HttpResponseError http_status=403 sdk_code=Forbidden")

    def test_unknown_provider_metadata_keeps_generic_ui_and_safe_log(self):
        error = RuntimeError("PRIVATE_MESSAGE https://PRIVATE_ENDPOINT/?key=PRIVATE_KEY")
        error.status_code = "401"
        error.error = SimpleNamespace(code="PRIVATE_KEY", message="PRIVATE_DOCUMENT")
        error.response = SimpleNamespace(status_code=True, headers={"PRIVATE_HEADER": "PRIVATE_KEY"}, body="PRIVATE_DOCUMENT", request=SimpleNamespace(url="https://PRIVATE_ENDPOINT/?key=PRIVATE_KEY"), text=Mock(side_effect=AssertionError("Do not read provider body")))
        app, log = self.exercise_failure(error, "unknown-offline-error")
        self.assertIn("Dokumen belum berhasil", app.error[0].value)
        self.assertEqual(log, "OCR failed: exception_type=RuntimeError http_status=unknown sdk_code=unknown")


if __name__ == "__main__":
    unittest.main()
