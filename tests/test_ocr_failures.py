from types import SimpleNamespace
import unittest

from pharmacheck_core import describe_ocr_failure


class OcrFailureTests(unittest.TestCase):
    def test_known_metadata_is_preserved_without_raw_exception_text(self):
        error_type = type("HttpResponseError", (Exception,), {})
        error = error_type("PRIVATE_MESSAGE https://PRIVATE_ENDPOINT/?key=PRIVATE_KEY")
        error.status_code = 403
        error.error = SimpleNamespace(code="Forbidden", message="PRIVATE_DOCUMENT_BODY")
        failure = describe_ocr_failure(error)
        self.assertEqual(failure.exception_type, "HttpResponseError")
        self.assertEqual(failure.http_status, 403)
        self.assertEqual(failure.sdk_code, "Forbidden")
        self.assertIn("aturan akses", failure.user_message)
        self.assertNotIn("PRIVATE", repr(failure))

    def test_unsafe_metadata_and_exception_formatting_are_ignored(self):
        class UnknownFailure(Exception):
            def __str__(self):
                raise AssertionError("Do not stringify provider exceptions")

        for invalid_status in ("401", True, 99, 600, SimpleNamespace(secret="PRIVATE")):
            with self.subTest(status_type=type(invalid_status).__name__):
                error = UnknownFailure()
                error.status_code = invalid_status
                error.error = SimpleNamespace(code="PRIVATE_KEY_ABC123", message="PRIVATE_BODY")
                failure = describe_ocr_failure(error)
                self.assertEqual(failure.exception_type, "ProviderError")
                self.assertIsNone(failure.http_status)
                self.assertIsNone(failure.sdk_code)
                self.assertIn("Dokumen belum berhasil", failure.user_message)
                self.assertNotIn("PRIVATE", repr(failure))

    def test_valid_response_status_drives_classification_without_body_reads(self):
        error = RuntimeError("PRIVATE_RAW_EXCEPTION")
        error.response = SimpleNamespace(status_code=429, body="PRIVATE_DOCUMENT")
        self.assertIn("membatasi permintaan", describe_ocr_failure(error).user_message)
        for status, fragment in ((401, "autentikasi"), (404, "tidak ditemukan"), (415, "Format dokumen"), (503, "sedang bermasalah"), (200, "Dokumen belum berhasil")):
            with self.subTest(status=status):
                error.response.status_code = status
                failure = describe_ocr_failure(error)
                self.assertEqual(failure.http_status, status)
                self.assertIn(fragment, failure.user_message)
                self.assertNotIn("PRIVATE", repr(failure))


if __name__ == "__main__":
    unittest.main()
