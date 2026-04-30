import streamlit as st
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from PIL import Image

# Konfigurasi Halaman Streamlit
st.set_page_config(
    page_title="PharmaCheck AI",
    page_icon="💊",
    layout="centered"
)

st.title("💊 PharmaCheck AI")
st.markdown("Unggah gambar dokumen atau label material farmasi untuk mengekstrak informasi penting seperti **Batch Number**, **Expire Date**, dan **Material Name** menggunakan Azure Document Intelligence.")

# Data Azure
ENDPOINT = st.secrets["AZURE_ENDPOINT"]
KEY = st.secrets["AZURE_KEY"]

# Inisialisasi Azure Client (di-cache agar tidak inisialisasi ulang terus-menerus)
@st.cache_resource
def get_azure_client():
    return DocumentAnalysisClient(
        endpoint=ENDPOINT, 
        credential=AzureKeyCredential(KEY)
    )

client = get_azure_client()

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
                
                # Struktur Data Default
                extracted_data = {
                    "Batch Number": "-",
                    "Expire Date": "-",
                    "Material Name": "-"
                }
                
                # Keyword matching
                batch_keywords = ["batch", "batch no", "batch number", "lot", "lot no"]
                expire_keywords = ["expire", "expire date", "exp", "exp date", "expiration", "ed", "kadaluarsa"]
                material_keywords = ["material", "material name", "product", "product name", "item", "nama"]
                
                other_fields = {}
                
                # Logika ekstraksi Key-Value
                if result.key_value_pairs:
                    for kv_pair in result.key_value_pairs:
                        if kv_pair.key:
                            key_text = kv_pair.key.content.lower().strip()
                            if key_text.endswith(':'):
                                key_text = key_text[:-1].strip()
                                
                            val_text = kv_pair.value.content if kv_pair.value else ""
                            
                            matched = False
                            for kw in batch_keywords:
                                if kw in key_text:
                                    extracted_data["Batch Number"] = val_text
                                    matched = True
                                    break
                            if not matched:
                                for kw in expire_keywords:
                                    if kw in key_text:
                                        extracted_data["Expire Date"] = val_text
                                        matched = True
                                        break
                            if not matched:
                                for kw in material_keywords:
                                    if kw in key_text:
                                        extracted_data["Material Name"] = val_text
                                        matched = True
                                        break
                                        
                            if not matched:
                                other_fields[kv_pair.key.content] = val_text
                
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

            except Exception as e:
                st.error(f"Terjadi kesalahan: {str(e)}")
