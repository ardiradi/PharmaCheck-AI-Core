# PharmaCheck AI

PharmaCheck is a Streamlit prototype that reads pharmaceutical labels and documents and presents candidate material names, batch numbers, and expiry dates for human review. Local Tesseract OCR is the default and needs no Azure account or API key. Azure Document Intelligence remains an explicitly selected optional route.

[Open the demo](https://ard11-pharmacheck-ai.hf.space/)

On 10 October 2026 the source added offline OCR after the owner reported the Azure resource inactive. Windows native tests read all three explicit labels on the existing synthetic sample and on an in-memory two-page PDF fixture. This replacement has not yet been deployed or verified in the Linux Space. The previous deployed image accepted uploads and previews, while its one real Azure processing attempt failed. See [local OCR evidence](evidence/local-ocr-2026-10-10.md) and the [deployment handoff](deploy/huggingface/DEPLOY.md).

![Public synthetic label](Gambar%20Test.jpeg)

## Workflow and limits

1. Upload JPG/JPEG, PNG, or PDF (maximum 10 MiB).
2. The local route decodes images or renders PDF pages at 300 DPI and reads them with English Tesseract OCR. Processing happens on the application server. Documents are not sent to Azure in this mode.
3. A conservative parser accepts explicit anchored labels such as `Material Name:`, `Batch Number:`, and `Expiry Date:`. It preserves recognized values without correcting identifiers or dates. A value can occupy the immediate next line; it never crosses a page boundary.
4. The interface shows candidates, raw OCR per page, and explicit missing or ambiguous fields. Repeated identical candidates are deduplicated; conflicting values are all retained.

Local processing allows at most five PDF pages and 12 megapixels per image/rendered page. Each OCR page has a 15-second recognition limit; the disposable worker has a 60-second total deadline and a 200,000-character raw-text cap. Linux workers additionally have a 2 GiB address-space ceiling. PDF parsing/rendering and OCR are isolated in a subprocess; temporary files are removed after completion or failure. The app does not keep a document database or audit history.

This is an extraction aid, not a quality release or medical decision tool. A recognized candidate is not a validated fact. On the sample, three explicit fields matched visual inspection, but other text was wrong: `50 mg` was read as `90 mg` in the original-file probe and `30 mg` after the application's RGB normalization. Do not use this prototype for dosage interpretation. One synthetic label and a simple PDF fixture do not establish general OCR accuracy. Layout, blur, rotation, language, punctuation, and multi-column documents can impair results.

## Implementation

- Streamlit 1.48.1, with CORS/XSRF defaults enabled and a 30-second WebSocket ping interval.
- `tesserocr==2.10.0`, a native Tesseract binding. The probed Windows build contains Tesseract 5.5.2; the Linux wheel's actual engine version must be recorded independently.
- Official English `tessdata_fast` model pinned to commit `87416418657359cb625c412a48b6e1d6d41c29bd` and SHA-256 `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2`.
- `pypdfium2==5.14.0` for PDF rasterization, with native objects closed explicitly inside the worker. PDFium is not shared across concurrent Streamlit threads.
- Pillow 10.2.0 for image validation, EXIF orientation, RGB conversion, and preview.
- Existing Azure SDK pins and historical key-value mapper retained for the optional Azure route. That route preserves its broad substring/last-match behavior; local parsing uses a separate conservative mapper.

## Run locally

Use Python 3.12 and an isolated virtual environment. On Debian, install `tesseract-ocr` and `tesseract-ocr-eng`, then install the pinned Python requirements. The Dockerfile builds a Linux image using available binary wheels and downloads/verifies the pinned English model at build time. The Docker tag is `python:3.12-slim`, not an immutable image digest.

```bash
python -m venv .venv
# Activate the environment for your platform.
python -m pip install -r requirements.txt
streamlit run app.py --server.maxUploadSize=10
```

Windows needs a native Tesseract binding matching the interpreter. The [tesserocr project](https://github.com/sirfz/tesserocr) links self-contained [Windows wheels](https://github.com/simonflueckiger/tesserocr-windows_build/releases/tag/tesserocr-v2.10.0-tesseract-5.5.2). For Python 3.12 x64 the verified wheel is `tesserocr-2.10.0-cp312-cp312-win_amd64.whl`, SHA-256 `e05d41a2b0e6f38f3a5195d05a73674d72152a775d1b8ebe481ca9306f94d27a`. Install that wheel into the venv before installing requirements; the matching Windows wheel is not available on PyPI for this release. Place the pinned official `eng.traineddata` in a dedicated directory and set `PHARMACHECK_TESSDATA` to that directory. This is a model path, not an API credential. Linux also searches standard distribution tessdata directories when this variable is absent.

```bash
python -m unittest discover -s tests -v
python -m pip check
```

Tests cover conservative candidates, worker isolation/limits/cleanup, native image and PDF OCR, local UI without Azure settings or network calls, and retained Azure startup/failure paths using fixtures. Historical [16-test](evidence/local-verification-2026-10-10.md), [18-test](evidence/runtime-compatibility-2026-10-10.md), and [23-test](evidence/ocr-diagnostics-2026-10-10.md) records remain dated evidence for earlier revisions. Current results and exact verification boundaries are in the [local OCR record](evidence/local-ocr-2026-10-10.md).

## Optional Azure route

Choose `Azure (opsional)` explicitly. Only this route resolves `AZURE_ENDPOINT` and `AZURE_KEY` (environment values before local Streamlit secrets) and constructs an Azure client. Missing/invalid settings stop that route with a sanitized setup message. Local failures never trigger Azure automatically. The owner reports the existing Azure resource inactive; no activation, account creation, billing change, or new genuine Azure request is part of this update.

Azure errors expose only a fixed safe message, validated HTTP status, and allowlisted SDK code. Local logs contain only a fixed error code. Raw exceptions, document text, credentials, request URLs, and traces are excluded from app diagnostics.

## Repository map

```text
app.py              Streamlit UI and explicit provider choice
pharmacheck_core.py  Local worker/parser plus historical Azure helpers
requirements.txt    Pinned Python dependencies
Gambar Test.jpeg    Public synthetic label
Dockerfile          Linux runtime, UID 1000, port 7860
deploy/huggingface/  Same six-file existing-Space handoff
tests/              Offline contracts, native OCR, and AppTest workflows
evidence/           Dated verification and historical boundaries
```
