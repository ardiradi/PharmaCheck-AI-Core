"""Local document OCR, conservative candidates, and optional Azure helpers."""

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping
from urllib.parse import urlsplit


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 5
MAX_PAGE_PIXELS = 12_000_000
MAX_RAW_CHARACTERS = 200_000
LOCAL_DEADLINE_SECONDS = 60
_LOCAL_MESSAGES = {
    "unsupported_type": "Gunakan file JPG, PNG, atau PDF.",
    "too_large": "Ukuran file melebihi batas 10 MiB.",
    "invalid_document": "Dokumen tidak dapat dibaca. Gunakan JPG, PNG, atau PDF yang valid dan tidak memerlukan kata sandi.",
    "too_many_pages": "PDF melebihi batas lima halaman. Unggah dokumen yang lebih pendek.",
    "pixel_limit": "Resolusi dokumen melebihi batas 12 megapiksel per halaman. Gunakan gambar atau halaman yang lebih kecil.",
    "timeout": "Pemrosesan mencapai batas waktu. Gunakan dokumen yang lebih pendek atau lebih sederhana.",
    "unavailable": "OCR lokal belum tersedia. Pemilik aplikasi perlu memeriksa instalasi mesin dan model bahasa Inggris.",
    "processing_failed": "Dokumen belum berhasil diproses. Periksa dokumen sumber dan coba file yang lebih sederhana.",
}


class LocalOcrError(ValueError):
    """A fixed code/message, never document content or a native exception."""

    def __init__(self, code: str):
        self.code = code if code in _LOCAL_MESSAGES else "processing_failed"
        super().__init__(_LOCAL_MESSAGES[self.code])


def parse_local_text(raw_pages: list[str]) -> dict:
    """Preserve OCR text and explicit candidates, without correcting values.

    Only anchored known labels are accepted, with a colon or an immediate
    following line. Conflicts remain ambiguous; source text is not a diagnosis.
    """
    import re

    aliases = {
        "Batch Number": ("batch number", "batch no", "batch no.", "lot number", "lot no", "lot no."),
        "Expire Date": ("expiry date", "expire date", "expiration date", "tanggal kedaluwarsa", "tanggal kadaluarsa"),
        "Material Name": ("material name", "product name", "nama material", "nama produk"),
    }
    lookup = {alias: field_name for field_name, names in aliases.items() for alias in names}
    labelled = re.compile(r"^\s*(" + "|".join(re.escape(name) for name in sorted(lookup, key=len, reverse=True)) + r")\s*:\s*(.*?)\s*$", re.IGNORECASE)
    candidates = {field_name: [] for field_name in aliases}
    for page in raw_pages:
        lines = page.splitlines()
        for index, line in enumerate(lines):
            match = labelled.fullmatch(line)
            if not match:
                continue
            field_name = lookup[match.group(1).casefold()]
            value = match.group(2).strip()
            if not value and index + 1 < len(lines):
                following = lines[index + 1].strip()
                # Do not consume another label, or an unrelated colon field.
                if following and ":" not in following and following.casefold().rstrip(":").strip() not in lookup:
                    value = following
            if value and value not in candidates[field_name]:
                candidates[field_name].append(value)
    fields = {}
    for name, values in candidates.items():
        status = "missing" if not values else "found" if len(values) == 1 else "ambiguous"
        fields[name] = {"status": status, "value": values[0] if status == "found" else None, "candidates": values}
    return {"raw_pages": list(raw_pages), "fields": fields}


def analyze_local_document(contents: bytes, media_type: str) -> dict:
    """Run native OCR/PDF rendering in a disposable, bounded subprocess.

    No Azure configuration, client, network API, or automatic provider fallback.
    PDFium is never shared between concurrent Streamlit threads.
    """
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    import tempfile

    if not isinstance(contents, bytes) or not contents:
        raise LocalOcrError("invalid_document")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise LocalOcrError("too_large")
    if media_type not in ("image/jpeg", "image/jpg", "image/png", "application/pdf"):
        raise LocalOcrError("unsupported_type")
    document_type = "pdf" if media_type == "application/pdf" else "image"
    # Pass only runtime necessities. Azure settings are not read or inherited.
    runtime_env = {name: os.environ[name] for name in (
        "SystemRoot", "SystemDrive", "WINDIR", "PATH", "TEMP", "TMP", "USERPROFILE",
        "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL", "PHARMACHECK_TESSDATA",
    ) if name in os.environ}
    runtime_env["OMP_THREAD_LIMIT"] = "1"
    with tempfile.TemporaryDirectory(prefix="pharmacheck-ocr-") as directory:
        input_path = Path(directory) / "document.bin"
        result_path = Path(directory) / "result.json"
        input_path.write_bytes(contents)
        command = [sys.executable, str(Path(__file__).resolve()), "--local-worker", str(input_path), document_type, str(result_path)]
        try:
            process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, timeout=LOCAL_DEADLINE_SECONDS,
                                     check=False, env=runtime_env)
        except subprocess.TimeoutExpired:
            raise LocalOcrError("timeout") from None
        except OSError:
            raise LocalOcrError("unavailable") from None
        if process.returncode != 0 or not result_path.exists() or result_path.stat().st_size > 4 * MAX_RAW_CHARACTERS + 1000:
            raise LocalOcrError("processing_failed")
        try:
            reply = json.loads(result_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raise LocalOcrError("processing_failed") from None
        if not isinstance(reply, dict):
            raise LocalOcrError("processing_failed")
        if "error" in reply:
            raise LocalOcrError(reply["error"] if type(reply["error"]) is str else "processing_failed")
        raw_pages = reply.get("raw_pages")
        if (type(raw_pages) is not list or not 1 <= len(raw_pages) <= MAX_PDF_PAGES
                or any(type(page) is not str for page in raw_pages)
                or sum(len(page) for page in raw_pages) > MAX_RAW_CHARACTERS):
            raise LocalOcrError("processing_failed")
        result = parse_local_text(raw_pages)
        result["provider"] = "Tesseract (local server)"
        return result


def _local_ocr_worker(input_path: str, document_type: str) -> list[str]:
    """Private subprocess implementation; all native objects stay here."""
    import math
    import os
    from pathlib import Path

    # Linux worker memory ceiling; Windows still has pixel/page/time bounds.
    if os.name == "posix":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 ** 3, 2 * 1024 ** 3))
    try:
        import tesserocr
        from PIL import Image, ImageOps
    except ImportError:
        raise LocalOcrError("unavailable") from None
    model_paths = [os.environ.get("PHARMACHECK_TESSDATA", ""),
                   "/usr/share/tesseract-ocr/5/tessdata", "/usr/share/tesseract-ocr/4.00/tessdata", "/usr/share/tessdata"]
    model_path = next((path for path in model_paths if path and (Path(path) / "eng.traineddata").is_file()), None)
    if model_path is None:
        raise LocalOcrError("unavailable")
    Image.MAX_IMAGE_PIXELS = MAX_PAGE_PIXELS
    pages = []

    def recognize(api, image):
        if image.width * image.height > MAX_PAGE_PIXELS:
            raise LocalOcrError("pixel_limit")
        api.SetImage(image)
        if not api.Recognize(timeout=15_000):
            raise LocalOcrError("timeout")
        text = api.GetUTF8Text()
        if len(text) + sum(map(len, pages)) > MAX_RAW_CHARACTERS:
            raise LocalOcrError("processing_failed")
        pages.append(text)
        api.Clear()

    try:
        with tesserocr.PyTessBaseAPI(path=model_path, lang="eng", oem=tesserocr.OEM.LSTM_ONLY, psm=tesserocr.PSM.AUTO) as api:
            if document_type == "image":
                with Image.open(input_path) as source:
                    if source.format not in ("PNG", "JPEG") or getattr(source, "n_frames", 1) != 1:
                        raise LocalOcrError("invalid_document")
                    if source.width * source.height > MAX_PAGE_PIXELS:
                        raise LocalOcrError("pixel_limit")
                    with ImageOps.exif_transpose(source).convert("RGB") as normalized:
                        recognize(api, normalized)
            elif document_type == "pdf":
                try:
                    import pypdfium2 as pdfium
                except ImportError:
                    raise LocalOcrError("unavailable") from None
                with pdfium.PdfDocument(input_path) as document:
                    if not 1 <= len(document) <= MAX_PDF_PAGES:
                        raise LocalOcrError("too_many_pages" if len(document) > MAX_PDF_PAGES else "invalid_document")
                    for index in range(len(document)):
                        page = document[index]
                        try:
                            width, height = page.get_size()
                            scale = 300 / 72
                            if not (math.isfinite(width) and math.isfinite(height)) or width <= 0 or height <= 0:
                                raise LocalOcrError("invalid_document")
                            if math.ceil(width * scale) * math.ceil(height * scale) > MAX_PAGE_PIXELS:
                                raise LocalOcrError("pixel_limit")
                            bitmap = page.render(scale=scale)
                            try:
                                with bitmap.to_pil().convert("RGB") as image:
                                    recognize(api, image)
                            finally:
                                bitmap.close()
                        finally:
                            page.close()
            else:
                raise LocalOcrError("unsupported_type")
    except LocalOcrError:
        raise
    except Image.DecompressionBombError:
        raise LocalOcrError("pixel_limit") from None
    except Exception:
        raise LocalOcrError("invalid_document") from None
    return pages


class AzureConfigurationError(ValueError):
    """A configuration message that never includes credential values."""


_SAFE_EXCEPTION_TYPES = frozenset({
    "AzureError", "ClientAuthenticationError", "HttpResponseError",
    "ResourceNotFoundError", "ServiceRequestError", "ServiceResponseError",
    "DecodeError", "DeserializationError", "ValueError", "TypeError",
    "TimeoutError", "OSError", "RuntimeError",
})
_SAFE_SDK_ERROR_CODES = frozenset({
    "InvalidRequest", "InvalidArgument", "Forbidden", "NotFound",
    "MethodNotAllowed", "Conflict", "UnsupportedMediaType",
    "InternalServerError", "ServiceUnavailable",
})
_GENERIC_OCR_MESSAGE = "Dokumen belum berhasil diproses sepenuhnya. Periksa format dokumen, konfigurasi Azure, dan ketersediaan layanan, lalu coba lagi."


@dataclass(frozen=True)
class OcrFailure:
    """Only fixed labels and validated status; never raw exception content."""

    exception_type: str
    http_status: int | None
    sdk_code: str | None
    user_message: str


def describe_ocr_failure(error: Exception) -> OcrFailure:
    """Read safe metadata without formatting an exception or reading its body."""

    def attribute(value, name):
        try:
            return getattr(value, name, None)
        except Exception:
            return None

    def status(value):
        # Reject strings, bools, unusual objects, and out-of-range values.
        return value if type(value) is int and 100 <= value <= 599 else None

    exception_type = type(error).__name__
    if exception_type not in _SAFE_EXCEPTION_TYPES:
        exception_type = "ProviderError"
    http_status = status(attribute(error, "status_code"))
    if http_status is None:
        http_status = status(attribute(attribute(error, "response"), "status_code"))
    code = attribute(attribute(error, "error"), "code")
    sdk_code = code if type(code) is str and code in _SAFE_SDK_ERROR_CODES else None

    messages = {
        401: "Layanan ekstraksi menolak autentikasi. Pemilik aplikasi perlu memeriksa kecocokan kredensial dan resource Azure.",
        403: "Akses layanan ekstraksi ditolak. Pemilik aplikasi perlu memeriksa izin dan aturan akses resource Azure.",
        404: "Layanan atau model ekstraksi tidak ditemukan. Pemilik aplikasi perlu memeriksa konfigurasi resource dan ketersediaan model.",
        415: "Format dokumen belum diterima layanan. Gunakan JPG, PNG, atau PDF yang valid.",
        429: "Layanan ekstraksi membatasi permintaan saat ini. Tunggu sebelum mencoba kembali.",
    }
    user_message = messages.get(http_status, _GENERIC_OCR_MESSAGE)
    if http_status is not None and 500 <= http_status <= 599:
        user_message = "Layanan ekstraksi sedang bermasalah. Coba kembali setelah layanan tersedia."
    return OcrFailure(exception_type, http_status, sdk_code, user_message)


@dataclass(frozen=True)
class AzureConfig:
    endpoint: str = field(repr=False)
    key: str = field(repr=False)


def resolve_azure_config(
    environ: Mapping[str, str],
    secret_getter: Callable[[str], object] | None = None,
) -> AzureConfig:
    """Prefer runtime environment values, then optional local Streamlit secrets."""

    def setting(name: str) -> str:
        value = environ.get(name, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
        if secret_getter is not None:
            try:
                value = secret_getter(name)
            except Exception:
                # Missing/malformed secrets files must not become raw UI errors.
                return ""
            if isinstance(value, str):
                return value.strip()
        return ""

    endpoint = setting("AZURE_ENDPOINT")
    key = setting("AZURE_KEY")
    missing = [name for name, value in (("AZURE_ENDPOINT", endpoint), ("AZURE_KEY", key)) if not value]
    if missing:
        raise AzureConfigurationError("Konfigurasi belum lengkap: " + ", ".join(missing) + ".")
    try:
        parsed = urlsplit(endpoint)
        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
        # Accessing port also checks invalid port strings/ranges.
        parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise AzureConfigurationError("AZURE_ENDPOINT harus berupa URL HTTPS layanan Azure tanpa kredensial atau query.")
    return AzureConfig(endpoint=endpoint, key=key)


def extract_fields(key_value_pairs: Iterable | None) -> tuple[dict[str, str], dict[str, str]]:
    """Map Azure key-value objects with the original keywords and match order.

    Substring matching and last-match-wins behavior are intentionally preserved.
    These mappings are not date validation, quality approval, or medical advice.
    """
    extracted_data = {"Batch Number": "-", "Expire Date": "-", "Material Name": "-"}
    keyword_groups = (
        ("Batch Number", ["batch", "batch no", "batch number", "lot", "lot no"]),
        ("Expire Date", ["expire", "expire date", "exp", "exp date", "expiration", "ed", "kadaluarsa"]),
        ("Material Name", ["material", "material name", "product", "product name", "item", "nama"]),
    )
    other_fields = {}
    for kv_pair in key_value_pairs or []:
        if not kv_pair.key:
            continue
        key_text = kv_pair.key.content.lower().strip()
        if key_text.endswith(":"):
            key_text = key_text[:-1].strip()
        val_text = kv_pair.value.content if kv_pair.value else ""
        for field_name, keywords in keyword_groups:
            if any(keyword in key_text for keyword in keywords):
                extracted_data[field_name] = val_text
                break
        else:
            other_fields[kv_pair.key.content] = val_text
    return extracted_data, other_fields


if __name__ == "__main__":
    import json
    from pathlib import Path
    import sys

    if len(sys.argv) != 5 or sys.argv[1] != "--local-worker":
        raise SystemExit(2)
    try:
        worker_reply = {"raw_pages": _local_ocr_worker(sys.argv[2], sys.argv[3])}
    except LocalOcrError as worker_error:
        worker_reply = {"error": worker_error.code}
    except Exception:
        worker_reply = {"error": "processing_failed"}
    Path(sys.argv[4]).write_text(json.dumps(worker_reply, ensure_ascii=False), encoding="utf-8")
