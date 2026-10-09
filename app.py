import logging
import os

import streamlit as st
from PIL import Image, ImageOps
from pharmacheck_core import (
    AzureConfigurationError, LocalOcrError, MAX_PAGE_PIXELS, MAX_UPLOAD_BYTES,
    analyze_local_document, describe_ocr_failure, extract_fields, resolve_azure_config,
)

_LOGGER = logging.getLogger("pharmacheck.ocr")
st.set_page_config(page_title="PharmaCheck AI", page_icon="💊", layout="centered")
st.title("💊 PharmaCheck AI")
st.markdown("Unggah label atau dokumen untuk membantu membaca **Batch Number**, **Expire Date**, dan **Material Name**.")
st.caption("Prototipe ekstraksi dokumen. Cocokkan hasil dengan sumber; aplikasi tidak membuat keputusan medis atau persetujuan kualitas.")
mode = st.radio("Mesin ekstraksi", ["OCR lokal (tanpa API key)", "Azure (opsional)"])
local_mode = mode == "OCR lokal (tanpa API key)"

if local_mode:
    st.info("Dokumen diproses oleh OCR di server aplikasi tanpa dikirim ke Azure. Hasil dapat salah atau tidak lengkap; teks mentah tersedia untuk diperiksa.")
else:
    st.info("Mode Azure mengirim dokumen ke Azure Document Intelligence. Pilih mode ini hanya jika pemilik aplikasi sudah menyediakan resource aktif.")


@st.cache_resource
def get_azure_client(endpoint, key):
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.formrecognizer import DocumentAnalysisClient
    return DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))


if not local_mode:
    try:
        config = resolve_azure_config(os.environ, lambda name: st.secrets[name])
    except AzureConfigurationError as error:
        st.warning(str(error))
        st.info("Pemilik aplikasi perlu mengatur AZURE_ENDPOINT dan AZURE_KEY di pengaturan rahasia aplikasi serta memastikan resource aktif. OCR belum dijalankan.")
        st.stop()
    try:
        client = get_azure_client(config.endpoint, config.key)
    except Exception:
        st.error("Layanan ekstraksi belum dapat diinisialisasi. Pemilik aplikasi perlu memeriksa konfigurasi Azure. OCR belum dijalankan.")
        st.stop()

st.caption("JPG/PNG atau PDF, maksimal 10 MiB. OCR lokal: maksimal 5 halaman PDF dan 12 megapiksel per halaman, batas pemrosesan 60 detik.")
uploaded_file = st.file_uploader("Pilih file gambar atau PDF", type=["jpg", "jpeg", "png", "pdf"])

if uploaded_file is not None:
    contents = uploaded_file.getvalue()
    if not contents or len(contents) > MAX_UPLOAD_BYTES:
        st.error(str(LocalOcrError("too_large" if len(contents) > MAX_UPLOAD_BYTES else "invalid_document")))
        st.stop()
    if uploaded_file.type in ("image/jpeg", "image/jpg", "image/png"):
        try:
            with Image.open(uploaded_file) as source:
                if source.format not in ("JPEG", "PNG") or getattr(source, "n_frames", 1) != 1:
                    raise LocalOcrError("invalid_document")
                if source.width * source.height > MAX_PAGE_PIXELS:
                    raise LocalOcrError("pixel_limit")
                with ImageOps.exif_transpose(source).convert("RGB") as preview:
                    st.image(preview, caption="Preview Dokumen", use_container_width=True)
        except LocalOcrError as error:
            st.error(str(error))
            st.stop()
        except Image.DecompressionBombError:
            st.error(str(LocalOcrError("pixel_limit")))
            st.stop()
        except Exception:
            st.error(str(LocalOcrError("invalid_document")))
            st.stop()
    elif uploaded_file.type == "application/pdf":
        st.info("PDF telah diunggah. OCR lokal membaca setiap halaman melalui gambar; hasil tetap perlu diperiksa terhadap PDF sumber.")
    else:
        st.error(str(LocalOcrError("unsupported_type")))
        st.stop()

    if st.button("Ekstrak Data Dokumen", type="primary"):
        with st.spinner("Membaca dokumen..."):
            try:
                if local_mode:
                    result = analyze_local_document(contents, uploaded_file.type)
                    fields = result["fields"]
                    values = {
                        name: item["value"] if item["status"] == "found" else
                        "Ambigu" if item["status"] == "ambiguous" else "Belum ditemukan"
                        for name, item in fields.items()
                    }
                    raw_pages = result["raw_pages"]
                    if not any(text.strip() for text in raw_pages):
                        st.warning("Tidak ada teks yang terbaca. Coba gambar yang lebih jelas dan periksa dokumen sumber.")
                    else:
                        st.success("OCR selesai. Periksa kandidat hasil terhadap dokumen sumber.")
                    unresolved = [name for name, item in fields.items() if item["status"] != "found"]
                    if unresolved:
                        st.warning("Field belum lengkap atau memiliki beberapa kandidat: " + ", ".join(unresolved) + ".")
                else:
                    poller = client.begin_analyze_document("prebuilt-document", document=contents)
                    result = poller.result()
                    values, other_fields = extract_fields(result.key_value_pairs)
                    raw_pages = ["\n".join(line.content for line in page.lines) for page in result.pages]
                    st.success("OCR selesai. Periksa hasil terhadap dokumen sumber.")

                st.subheader("🔍 Kandidat Informasi Kunci")
                columns = st.columns(3)
                for column, name in zip(columns, ("Batch Number", "Expire Date", "Material Name")):
                    column.metric(name, values[name])
                st.caption("Tanggal dan identifier ditampilkan sebagaimana dibaca. Nilai tidak dinormalisasi atau dinyatakan benar secara otomatis.")
                with st.expander("📄 Kandidat dan status field" if local_mode else "📄 Field Lainnya (Key-Value)"):
                    st.json(fields if local_mode else other_fields)
                with st.expander("📝 Teks Mentah OCR"):
                    for index, text in enumerate(raw_pages, start=1):
                        st.caption(f"Halaman {index}")
                        st.text(text if text.strip() else "Tidak ada teks yang terbaca pada halaman ini.")
            except LocalOcrError as error:
                _LOGGER.error("Local OCR failed: code=%s", error.code, exc_info=False, stack_info=False)
                st.error(str(error))
            except Exception as error:
                if local_mode:
                    _LOGGER.error("Local OCR failed: code=processing_failed", exc_info=False, stack_info=False)
                    st.error(str(LocalOcrError("processing_failed")))
                else:
                    failure = describe_ocr_failure(error)
                    _LOGGER.error(
                        "OCR failed: exception_type=%s http_status=%s sdk_code=%s",
                        failure.exception_type,
                        failure.http_status if failure.http_status is not None else "unknown",
                        failure.sdk_code or "unknown", exc_info=False, stack_info=False,
                    )
                    st.error(failure.user_message)
