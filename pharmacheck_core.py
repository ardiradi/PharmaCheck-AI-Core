"""Configuration and existing field mapping, independent of Streamlit and Azure."""

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping
from urllib.parse import urlsplit


class AzureConfigurationError(ValueError):
    """A configuration message that never includes credential values."""


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
