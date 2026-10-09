"""Configuration, field mapping, and safe failure metadata without SDK imports."""

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping
from urllib.parse import urlsplit


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
