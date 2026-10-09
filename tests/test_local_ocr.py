"""Local OCR contract tests; document fixtures contain synthetic public text."""

import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import pharmacheck_core as core


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_TEXT = (
    "Material Name: APRELOX\n"
    "Batch Number: APL441098\n"
    "Expiry Date: 12/2026\n"
)
SAFE_CODES = {
    "unsupported_type", "too_large", "invalid_document", "too_many_pages",
    "pixel_limit", "timeout", "unavailable", "processing_failed",
}
PRIVATE_MARKER = "PRIVATE_FAKE_DOCUMENT_CONTENT"
HAS_NATIVE_OCR = (
    importlib.util.find_spec("tesserocr") is not None
    and importlib.util.find_spec("pypdfium2") is not None
    and importlib.util.find_spec("PIL") is not None
)
HAS_APP_DEPS = (
    importlib.util.find_spec("streamlit") is not None
    and importlib.util.find_spec("azure") is not None
    and importlib.util.find_spec("PIL") is not None
)


def minimal_pdf(page_lines, width=612, height=792):
    """Generate an in-memory Helvetica PDF, including a valid xref table."""
    page_ids = [4 + 2 * index for index in range(len(page_lines))]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            "<< /Type /Pages /Kids ["
            + " ".join(f"{page_id} 0 R" for page_id in page_ids)
            + f"] /Count {len(page_lines)} >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for page_id, lines in zip(page_ids, page_lines):
        objects.append((
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>"
        ).encode("ascii"))
        commands = ["BT", "/F1 24 Tf", f"50 {height - 70} Td"]
        for index, line in enumerate(lines):
            if index:
                commands.append("0 -50 Td")
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj")
        commands.append("ET")
        stream = ("\n".join(commands) + "\n").encode("ascii")
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream + b"endstream"
        )

    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, body in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{object_id} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend((
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii"))
    return bytes(document)


class LocalTextParserTests(unittest.TestCase):
    def assert_field(self, result, name, status, value, candidates):
        self.assertEqual(result["fields"][name], {
            "status": status, "value": value, "candidates": candidates,
        })

    def assert_sample(self, result):
        for name, value in (
            ("Material Name", "APRELOX"),
            ("Batch Number", "APL441098"),
            ("Expire Date", "12/2026"),
        ):
            self.assert_field(result, name, "found", value, [value])

    def test_labeled_sample_and_raw_pages_are_preserved(self):
        pages = [SAMPLE_TEXT, "Unrelated text\n\n"]
        original = list(pages)
        result = core.parse_local_text(pages)
        self.assert_sample(result)
        self.assertEqual(result["raw_pages"], original)
        self.assertEqual(pages, original)

    def test_missing_fields_are_explicit(self):
        result = core.parse_local_text(["No recognized labels\n"])
        for name in ("Material Name", "Batch Number", "Expire Date"):
            self.assert_field(result, name, "missing", None, [])

    def test_immediate_next_line_values(self):
        result = core.parse_local_text([
            "Material Name:\nAPRELOX\nBatch No.:\nAPL441098\nExpiry Date:\n12/2026\n"
        ])
        self.assert_sample(result)

    def test_supported_label_aliases_and_case(self):
        for material in ("Material Name", "Product Name", "Nama Material"):
            for batch in ("Batch Number", "Batch No", "Batch No."):
                for expiry in ("Expiry Date", "Expire Date", "Expiration Date", "Tanggal Kedaluwarsa"):
                    with self.subTest(material=material, batch=batch, expiry=expiry):
                        text = f"{material.upper()}: APRELOX\n{batch.lower()}: APL441098\n{expiry}: 12/2026\n"
                        self.assert_sample(core.parse_local_text([text]))

    def test_identical_candidates_are_deduplicated_across_pages(self):
        result = core.parse_local_text([SAMPLE_TEXT, SAMPLE_TEXT])
        self.assert_sample(result)

    def test_conflicting_values_are_preserved_instead_of_overwritten(self):
        result = core.parse_local_text([
            SAMPLE_TEXT,
            "Batch No.: SECOND123\nBatch Number: APL441098\nExpiry Date: 01/2027\n",
        ])
        self.assert_field(result, "Batch Number", "ambiguous", None, ["APL441098", "SECOND123"])
        self.assert_field(result, "Expire Date", "ambiguous", None, ["12/2026", "01/2027"])
        self.assert_field(result, "Material Name", "found", "APRELOX", ["APRELOX"])

    def test_substrings_and_embedded_labels_do_not_become_fields(self):
        result = core.parse_local_text([
            "Manufactured: 01/2025\nApproved by: Someone\nPilot: PILOT123\n"
            "Export code: EXP123\nNote Material Name: APRELOX\n"
        ])
        for name in ("Material Name", "Batch Number", "Expire Date"):
            self.assert_field(result, name, "missing", None, [])

    def test_ocr_character_confusions_are_never_silently_corrected(self):
        result = core.parse_local_text([
            "Material Name: APREL0X\nBatch Number: APL44I098\nExpiry Date: 12/2O26\n"
        ])
        for name, value in (
            ("Material Name", "APREL0X"),
            ("Batch Number", "APL44I098"),
            ("Expire Date", "12/2O26"),
        ):
            self.assert_field(result, name, "found", value, [value])

    def test_a_following_label_is_not_consumed_as_the_previous_value(self):
        result = core.parse_local_text(["Batch No.:\nExpiry Date: 12/2026\n"])
        self.assert_field(result, "Batch Number", "missing", None, [])
        self.assert_field(result, "Expire Date", "found", "12/2026", ["12/2026"])

    def test_next_line_does_not_skip_blanks_or_cross_page_boundaries(self):
        for pages in (["Batch Number:\n\nAPL441098\n"], ["Batch Number:\n", "APL441098\n"]):
            with self.subTest(pages=pages):
                result = core.parse_local_text(pages)
                self.assert_field(result, "Batch Number", "missing", None, [])


class LocalWorkerContractTests(unittest.TestCase):
    def assert_safe_error(self, function, expected=None):
        with self.assertRaises(core.LocalOcrError) as captured:
            function()
        error = captured.exception
        self.assertIn(error.code, SAFE_CODES)
        if expected is not None:
            self.assertEqual(error.code, expected)
        self.assertNotIn(PRIVATE_MARKER, str(error))
        self.assertNotIn(PRIVATE_MARKER, repr(error))
        return error

    @staticmethod
    def worker_reply(reply, returncode=0):
        def run(argv, **kwargs):
            Path(argv[-1]).write_text(json.dumps(reply), encoding="utf-8")
            return subprocess.CompletedProcess(argv, returncode)
        return run

    def test_declared_resource_limits(self):
        self.assertEqual(core.MAX_UPLOAD_BYTES, 10 * 1024 * 1024)
        self.assertEqual(core.MAX_PDF_PAGES, 5)
        self.assertEqual(core.MAX_PAGE_PIXELS, 12_000_000)

    def test_unsupported_type_is_rejected_before_starting_a_worker(self):
        with patch("subprocess.run") as run:
            self.assert_safe_error(
                lambda: core.analyze_local_document(b"text", "text/plain"), "unsupported_type"
            )
        run.assert_not_called()

    def test_upload_limit_is_enforced_before_starting_a_worker(self):
        with patch("subprocess.run") as run:
            self.assert_safe_error(
                lambda: core.analyze_local_document(b"x" * (core.MAX_UPLOAD_BYTES + 1), "image/png"),
                "too_large",
            )
        run.assert_not_called()

    def test_worker_success_uses_isolation_deadline_and_private_output_channels(self):
        payload = b"image bytes passed only to the worker"
        request_paths = []

        def run(argv, **kwargs):
            self.assertEqual(argv[2], "--local-worker")
            self.assertTrue(Path(argv[1]).is_absolute())
            self.assertEqual(argv[-2], "image")
            self.assertEqual(Path(argv[-3]).read_bytes(), payload)
            self.assertEqual(kwargs["timeout"], 60)
            self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
            self.assertFalse(kwargs.get("shell", False))
            request_paths.extend((Path(argv[-3]), Path(argv[-1])))
            Path(argv[-1]).write_text(json.dumps({"raw_pages": [SAMPLE_TEXT]}), encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0)

        with patch("subprocess.run", side_effect=run) as process:
            result = core.analyze_local_document(payload, "image/jpeg")
        process.assert_called_once()
        self.assertEqual(result["provider"], "Tesseract (local server)")
        self.assertEqual(result["raw_pages"], [SAMPLE_TEXT])
        self.assertEqual(result["fields"]["Batch Number"]["value"], "APL441098")
        self.assertTrue(request_paths)
        self.assertTrue(all(not path.exists() for path in request_paths))

    def test_timeout_never_exposes_child_output_and_cleans_input(self):
        request_paths = []

        def timeout(argv, **kwargs):
            request_paths.append(Path(argv[-3]))
            raise subprocess.TimeoutExpired(argv, 60, output=PRIVATE_MARKER, stderr=PRIVATE_MARKER)

        with patch("subprocess.run", side_effect=timeout):
            self.assert_safe_error(
                lambda: core.analyze_local_document(b"image", "image/png"), "timeout"
            )
        self.assertTrue(all(not path.exists() for path in request_paths))

    def test_fixed_worker_failure_codes_survive_without_raw_details(self):
        for code in SAFE_CODES:
            with self.subTest(code=code), patch(
                "subprocess.run", side_effect=self.worker_reply({"error": code, "detail": PRIVATE_MARKER})
            ):
                self.assert_safe_error(
                    lambda: core.analyze_local_document(b"image", "image/png"), code
                )

    def test_unknown_worker_code_is_replaced_by_a_safe_failure(self):
        with patch("subprocess.run", side_effect=self.worker_reply({"error": PRIVATE_MARKER})):
            self.assert_safe_error(
                lambda: core.analyze_local_document(b"image", "image/png"), "processing_failed"
            )

    def test_crashed_worker_is_rejected_even_if_a_success_reply_exists(self):
        with patch("subprocess.run", side_effect=self.worker_reply({"raw_pages": [SAMPLE_TEXT]}, returncode=9)):
            self.assert_safe_error(
                lambda: core.analyze_local_document(b"image", "image/png"), "processing_failed"
            )

    def test_invalid_reply_shapes_and_excessive_raw_text_are_rejected(self):
        for reply in ({}, {"raw_pages": PRIVATE_MARKER}, {"raw_pages": [7]}, {"raw_pages": ["x" * 200_001]}):
            with self.subTest(reply_kind=str(type(reply.get("raw_pages")))), patch(
                "subprocess.run", side_effect=self.worker_reply(reply)
            ):
                self.assert_safe_error(lambda: core.analyze_local_document(b"image", "image/png"))

    def test_invalid_json_does_not_expose_worker_content(self):
        def invalid_reply(argv, **kwargs):
            Path(argv[-1]).write_text(PRIVATE_MARKER, encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0)

        with patch("subprocess.run", side_effect=invalid_reply):
            self.assert_safe_error(
                lambda: core.analyze_local_document(b"image", "image/png"), "processing_failed"
            )


@unittest.skipUnless(HAS_NATIVE_OCR, "Install the pinned local OCR dependencies to exercise native workers")
class NativeLocalOcrTests(unittest.TestCase):
    def setUp(self):
        # The scoped Windows probe supplies the same pinned English model as
        # Docker. Keep this override local to each test; Linux can use its own
        # configured/default model directory when the probe is absent.
        probe = ROOT.parent / "tmp" / "pharmacheck-tesseract-probe" / "tessdata"
        if (probe / "eng.traineddata").is_file():
            runtime = patch.dict(os.environ, {"PHARMACHECK_TESSDATA": str(probe)})
            runtime.start()
            self.addCleanup(runtime.stop)

    def assert_sample(self, result):
        self.assertEqual(result["provider"], "Tesseract (local server)")
        for name, value in (
            ("Material Name", "APRELOX"),
            ("Batch Number", "APL441098"),
            ("Expire Date", "12/2026"),
        ):
            self.assertEqual(result["fields"][name], {
                "status": "found", "value": value, "candidates": [value],
            })

    def assert_error(self, contents, media_type, expected):
        with self.assertRaises(core.LocalOcrError) as captured:
            core.analyze_local_document(contents, media_type)
        self.assertEqual(captured.exception.code, expected)
        self.assertNotIn(PRIVATE_MARKER, str(captured.exception))

    def test_original_jpeg_recognizes_the_three_visible_sample_values(self):
        contents = (ROOT / "Gambar Test.jpeg").read_bytes()
        result = core.analyze_local_document(contents, "image/jpeg")
        self.assert_sample(result)
        self.assertEqual(len(result["raw_pages"]), 1)
        for value in ("APRELOX", "APL441098", "12/2026"):
            self.assertIn(value, result["raw_pages"][0])

    def test_two_page_pdf_is_rasterized_and_recognized_in_page_order(self):
        contents = minimal_pdf([
            ["Material Name: APRELOX", "Batch Number: APL441098"],
            ["Expiry Date: 12/2026", "Batch Number: APL441098"],
        ])
        result = core.analyze_local_document(contents, "application/pdf")
        self.assert_sample(result)
        self.assertEqual(len(result["raw_pages"]), 2)
        self.assertIn("APRELOX", result["raw_pages"][0])
        self.assertIn("12/2026", result["raw_pages"][1])

    def test_pdf_page_limit_is_enforced(self):
        self.assert_error(minimal_pdf([[]] * 6), "application/pdf", "too_many_pages")

    def test_corrupt_pdf_is_rejected_without_exposing_its_contents(self):
        self.assert_error(
            b"%PDF-1.4\n" + PRIVATE_MARKER.encode("ascii"), "application/pdf", "invalid_document"
        )

    def test_pdf_pixel_limit_is_checked_before_rendering_a_giant_page(self):
        self.assert_error(
            minimal_pdf([[]], width=4000, height=4000), "application/pdf", "pixel_limit"
        )

    def test_image_pixel_limit_is_enforced(self):
        from PIL import Image

        contents = BytesIO()
        with Image.new("1", (4001, 3000), 1) as image:
            image.save(contents, format="PNG")
        self.assert_error(contents.getvalue(), "image/png", "pixel_limit")

    def test_corrupt_image_is_rejected_without_exposing_its_contents(self):
        self.assert_error(PRIVATE_MARKER.encode("ascii"), "image/jpeg", "invalid_document")


@unittest.skipUnless(HAS_APP_DEPS, "Install the pinned UI dependencies for local-mode AppTest")
class LocalOcrAppTests(unittest.TestCase):
    def test_default_upload_and_button_preserve_raw_conflicts_without_azure_or_network(self):
        from contextlib import ExitStack

        from PIL import Image
        import streamlit as st
        from streamlit.proto.Common_pb2 import FileURLs
        from streamlit.runtime.uploaded_file_manager import UploadedFile, UploadedFileRec
        from streamlit.testing.v1 import AppTest

        image_bytes = BytesIO()
        with Image.new("RGB", (2, 2), "white") as image:
            image.save(image_bytes, format="PNG")
        payload = image_bytes.getvalue()
        raw_pages = [SAMPLE_TEXT + "Batch Number: SECOND123\n"]
        reply = core.parse_local_text(raw_pages)
        reply["provider"] = "Tesseract (local server)"
        real_uploader = st.file_uploader

        def offline_upload(*args, **kwargs):
            # AppTest has no uploader setter in Streamlit 1.48.1. Keep its real
            # widget rendering, and supply a fresh real UploadedFile each run.
            real_uploader(*args, **kwargs)
            return UploadedFile(
                UploadedFileRec("offline-image", "offline.png", "image/png", payload),
                FileURLs(),
            )

        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"AZURE_ENDPOINT": "", "AZURE_KEY": ""}))
            stack.enter_context(patch("streamlit.config.get_config_files", return_value=[]))
            secret_read = stack.enter_context(patch(
                "streamlit.runtime.secrets.Secrets._parse_file_path",
                side_effect=AssertionError("Local mode must not read secret files"),
            ))
            secret_get = stack.enter_context(patch(
                "streamlit.runtime.secrets.Secrets.__getitem__",
                side_effect=AssertionError("Local mode must not inspect secrets"),
            ))
            connect = stack.enter_context(patch(
                "socket.socket.connect", side_effect=AssertionError("Local mode must not access the network")
            ))
            azure_config = stack.enter_context(patch.object(
                core, "resolve_azure_config", side_effect=AssertionError("Local mode must not resolve Azure configuration")
            ))
            azure_client = stack.enter_context(patch(
                "azure.ai.formrecognizer.DocumentAnalysisClient",
                side_effect=AssertionError("Local mode must not create an Azure client"),
            ))
            analyze = stack.enter_context(patch.object(core, "analyze_local_document", return_value=reply))
            stack.enter_context(patch.object(st, "file_uploader", side_effect=offline_upload))

            app = AppTest.from_file(str(ROOT / "app.py"))
            app.secrets = {"offline_fixture": True}
            app.run(timeout=15)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.radio[0].value, "OCR lokal (tanpa API key)")
            self.assertEqual(len(app.get("file_uploader")), 1)
            self.assertEqual(len(app.get("imgs")), 1)
            analyze.assert_not_called()

            app.button[0].click().run(timeout=15)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.error), 0)
            analyze.assert_called_once_with(payload, "image/png")
            metrics = {metric.label: metric.value for metric in app.metric}
            self.assertEqual(metrics, {
                "Batch Number": "Ambigu", "Expire Date": "12/2026", "Material Name": "APRELOX",
            })
            self.assertTrue(any("Batch Number" in warning.value for warning in app.warning))
            self.assertEqual(len(app.text), 1)
            self.assertIn(SAMPLE_TEXT.strip(), app.text[0].value)
            self.assertIn("Batch Number: SECOND123", app.text[0].value)
            candidate_json = app.json[0].value
            if isinstance(candidate_json, str):
                candidate_json = json.loads(candidate_json)
            self.assertEqual(candidate_json["Batch Number"], {
                "status": "ambiguous", "value": None, "candidates": ["APL441098", "SECOND123"],
            })

            for blocked in (secret_read, secret_get, connect, azure_config, azure_client):
                blocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
