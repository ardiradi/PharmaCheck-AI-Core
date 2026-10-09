import os

import streamlit as st
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from PIL import Image
from pharmacheck_core import AzureConfigurationError, extract_fields, resolve_azure_config

# Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="PharmaCheck AI",
    page_icon="💊",
    layout="centered"
)

st.title("💊 PharmaCheck AI")
st.markdown("Unggah gambar dokumen atau label material farmasi untuk mengekstrak informasi penting seperti **Batch Number**, **Expire Date**, dan **Material Name** menggunakan Azure Document Intelligence.")

st.caption("Prototipe ekstraksi dokumen. Periksa hasil terhadap dokumen sumber; aplikasi tidak membuat keputusan medis atau persetujuan kualitas.")

# Inisialisasi Azure Client (di-cache agar tidak inisialisasi ulang terus-menerus)
@st.cache_resource
def get_azure_client(endpoint, key):
    return DocumentAnalysisClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    )

try:
    config = resolve_azure_config(os.environ, lambda name: st.secrets[name])
except AzureConfigurationError as error:
    st.warning(str(error))
    st.info("Pemilik aplikasi perlu mengatur AZURE_ENDPOINT dan AZURE_KEY di Space Settings → Secrets atau .streamlit/secrets.toml lokal. OCR belum dijalankan.")
    st.stop()

try:
    client = get_azure_client(config.endpoint, config.key)
except Exception:
    st.error("Layanan ekstraksi belum dapat diinisialisasi. Pemilik aplikasi perlu memeriksa konfigurasi Azure. OCR belum dijalankan.")
    st.stop()

# Komponen Upload File
uploaded_file = st.file_uploader("Pilih file gambar atau PDF", type=["jpg", "jpeg", "png", "pdf"])

if uploaded_file is not None:
    # Jika file adalah gambar, tampilkan preview-nya
    if uploaded_file.type in ["image/jpeg", "image/png", "image/jpg"]:
        image = Image.open(uploaded_file)
        st.image(image, caption="Preview Dokumen", use_column_width=True)
    elif uploaded_file.type == "application/pdf":
        st.info("File PDF telah diunggah.")
        
    # Tombol Ekstrak
    if st.button("Ekstrak Data Dokumen", type="primary"):
        with st.spinner('Menganalisis dokumen dengan Azure Document Intelligence...'):
            try:
                # Ambil isi (bytes) dari file yang diupload
                contents = uploaded_file.getvalue()
                
                # Menggunakan "prebuilt-document" untuk mendapatkan Form Fields (Key-Value)
                poller = client.begin_analyze_document("prebuilt-document", document=contents)
                result = poller.result()
                
                # Kata kunci dan urutan pencocokan historis dipertahankan.
                extracted_data, other_fields = extract_fields(result.key_value_pairs)
                
                st.success("Ekstraksi berhasil!")
                
                # Tampilan UI Hasil Utama
                st.subheader("🔍 Informasi Kunci")
                col1, col2, col3 = st.columns(3)
                
                # Tampilkan sebagai metrik agar menonjol
                col1.metric("Batch Number", extracted_data["Batch Number"])
                col2.metric("Expire Date", extracted_data["Expire Date"])
                col3.metric("Material Name", extracted_data["Material Name"])
                
                st.divider()
                
                # Tampilan Expandable (Akordion) untuk detail lainnya
                with st.expander("📄 Lihat Field Lainnya (Key-Value)"):
                    if other_fields:
                        st.json(other_fields)
                    else:
                        st.info("Tidak ada form field tambahan yang ditemukan.")
                        
                with st.expander("📝 Lihat Teks Mentah (Raw Text OCR)"):
                    raw_text = ""
                    for page in result.pages:
                        for line in page.lines:
                            raw_text += line.content + "\n"
                    st.text(raw_text)

            except Exception:
                st.error("Dokumen belum berhasil diproses sepenuhnya. Periksa format dokumen, konfigurasi Azure, dan ketersediaan layanan, lalu coba lagi.")
