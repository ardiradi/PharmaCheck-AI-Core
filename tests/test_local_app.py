"""Exercise local default and real Streamlit button without Azure access."""
import importlib.util
from io import BytesIO
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import pharmacheck_core as core

ROOT = Path(__file__).resolve().parents[1]
HAS_APP = importlib.util.find_spec("streamlit") is not None
HAS_NATIVE = importlib.util.find_spec("tesserocr") is not None


@unittest.skipUnless(HAS_APP, "Install pinned application dependencies")
class LocalAppTests(unittest.TestCase):
    def exercise(self, contents=None, media_type="image/png", mocked_pages=None):
        import streamlit as st
        from streamlit.proto.Common_pb2 import FileURLs
        from streamlit.runtime.uploaded_file_manager import UploadedFile, UploadedFileRec
        from streamlit.testing.v1 import AppTest
        from contextlib import ExitStack

        real_uploader = st.file_uploader
        def offline_upload(*args, **kwargs):
            real_uploader(*args, **kwargs)
            if contents is None:
                return None
            return UploadedFile(UploadedFileRec("local-fixture", "synthetic.png", media_type, contents), FileURLs())

        app = AppTest.from_file(str(ROOT / "app.py"))
        app.secrets = {"offline_fixture": True}
        with ExitStack() as stack:
            resolver = stack.enter_context(patch("pharmacheck_core.resolve_azure_config", side_effect=AssertionError("Local mode must not resolve Azure settings")))
            client = stack.enter_context(patch("azure.ai.formrecognizer.DocumentAnalysisClient", side_effect=AssertionError("No Azure client in local mode")))
            secret = stack.enter_context(patch("streamlit.runtime.secrets.Secrets._parse_file_path", side_effect=AssertionError("No secret file reads")))
            connect = stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("No network in local test")))
            stack.enter_context(patch("streamlit.config.get_config_files", return_value=[]))
            stack.enter_context(patch("streamlit.file_uploader", side_effect=offline_upload))
            stack.enter_context(patch.dict(os.environ, {"AZURE_ENDPOINT": "PRIVATE_UNUSED_ENDPOINT", "AZURE_KEY": "PRIVATE_UNUSED_KEY"}, clear=False))
            analyzer = None
            if mocked_pages is not None:
                reply = core.parse_local_text(mocked_pages)
                reply["provider"] = "Tesseract (local server)"
                analyzer = stack.enter_context(patch("pharmacheck_core.analyze_local_document", return_value=reply))
            app.run(timeout=15)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.radio[0].value, "OCR lokal (tanpa API key)")
            self.assertEqual(len(app.get("file_uploader")), 1)
            if contents is not None:
                self.assertEqual(len(app.get("imgs")), 1)
                self.assertEqual(len(app.success), 0)
                if analyzer is not None:
                    analyzer.assert_not_called()
                app.button[0].click().run(timeout=20)
                if analyzer is not None:
                    analyzer.assert_called_once_with(contents, media_type)
            resolver.assert_not_called()
            client.assert_not_called()
            secret.assert_not_called()
            connect.assert_not_called()
        self.assertEqual(len(app.exception), 0)
        for kind in ("markdown", "caption", "text", "info", "warning", "error", "success"):
            for element in app.get(kind):
                self.assertNotIn("PRIVATE_UNUSED", str(getattr(element, "value", "")))
        return app

    @staticmethod
    def png():
        from PIL import Image
        data = BytesIO()
        with Image.new("RGB", (20, 20), "white") as image:
            image.save(data, format="PNG")
        return data.getvalue()

    def test_default_reaches_uploader_without_azure_settings_or_client(self):
        app = self.exercise()
        self.assertEqual(len(app.error), 0)
        self.assertEqual(len(app.warning), 0)

    def test_conflicting_candidates_and_missing_field_are_visible_with_raw_text(self):
        pages = ["Material Name: APREL0X\nBatch Number: FIRST\nBatch Number: SECOND\n"]
        app = self.exercise(self.png(), mocked_pages=pages)
        metrics = {item.label: item.value for item in app.metric}
        self.assertEqual(metrics, {"Batch Number": "Ambigu", "Expire Date": "Belum ditemukan", "Material Name": "APREL0X"})
        self.assertTrue(any("belum lengkap" in item.value for item in app.warning))
        self.assertEqual(app.text[0].value, pages[0].rstrip("\n"))
        self.assertEqual(len(app.error), 0)

    def test_empty_ocr_has_explicit_warning_and_no_success(self):
        app = self.exercise(self.png(), mocked_pages=[""])
        self.assertEqual(len(app.success), 0)
        self.assertTrue(any("Tidak ada teks" in item.value for item in app.warning))
        self.assertTrue(all(item.value == "Belum ditemukan" for item in app.metric))

    @unittest.skipUnless(HAS_NATIVE, "Install native OCR for real local UI test")
    def test_actual_uploaded_jpeg_button_displays_real_ocr_candidates(self):
        app = self.exercise((ROOT / "Gambar Test.jpeg").read_bytes(), "image/jpeg")
        self.assertEqual({item.label: item.value for item in app.metric}, {
            "Batch Number": "APL441098", "Expire Date": "12/2026", "Material Name": "APRELOX",
        })
        self.assertEqual(len(app.error), 0)
        self.assertTrue(any("APRELOX" in item.value for item in app.text))


class LocalLabelGuardTests(unittest.TestCase):
    def test_next_line_without_colon_does_not_turn_a_label_into_a_value(self):
        result = core.parse_local_text(["Material Name:\nBatch Number\nAPL441098\n"])
        self.assertEqual(result["fields"]["Material Name"], {
            "status": "missing", "value": None, "candidates": [],
        })
        self.assertEqual(result["fields"]["Batch Number"]["status"], "missing")

    @unittest.skipUnless(HAS_NATIVE, "Install native OCR for oversized-image classification")
    def test_decompression_bomb_is_classified_as_pixel_limit(self):
        from PIL import Image
        contents = BytesIO()
        with Image.new("1", (5001, 5000), 1) as image:
            image.save(contents, format="PNG")
        with self.assertRaises(core.LocalOcrError) as failure:
            core.analyze_local_document(contents.getvalue(), "image/png")
        self.assertEqual(failure.exception.code, "pixel_limit")


if __name__ == "__main__":
    unittest.main()
