# PharmaCheck AI

PharmaCheck AI is a Streamlit prototype for extracting important fields from pharmaceutical labels and documents with Azure AI Document Intelligence.

[Open the live demo](https://ard11-pharmacheck-ai.hf.space/)

On 10 October 2026 the initial Docker migration reached Running with successful root and health checks, but the public sample upload returned HTTP 400 before OCR. This repository now contains a [tested Streamlit compatibility update](evidence/runtime-compatibility-2026-10-10.md) and the [existing-Space handoff](deploy/huggingface/DEPLOY.md). The initial HTTP checks do not establish a working extraction flow; verification of the updated live upload and genuine OCR remains pending.

![Sample pharmaceutical label used to test the extraction flow](Gambar%20Test.jpeg)

## Problem

Material labels can contain operationally important values such as a material name, batch number, and expiry date. Reading these fields manually is repetitive and a single transcription mistake can cause downstream problems.

This prototype makes those values easier to inspect. It does not make release, quality, or medical decisions.

## What the prototype does

1. Accepts a JPG, JPEG, PNG, or PDF upload.
2. Sends the document bytes to Azure's `prebuilt-document` model.
3. Matches returned key-value pairs against explicit keyword groups.
4. Shows the material name, batch number, and expiry date as primary fields.
5. Keeps other key-value fields and raw OCR text available for human review.

## Implementation

- Python and Streamlit for the interface
- Azure AI Document Intelligence (`azure-ai-formrecognizer`) for OCR and key-value extraction
- Pillow for local image previews
- Streamlit resource caching for the Azure client

The field mapping is intentionally transparent: `pharmacheck_core.py` contains the original keyword lists and matching order used to classify extracted keys. Configuration resolution is independent of Streamlit so missing/invalid settings can be tested without Azure requests.

## Run locally

```bash
git clone https://github.com/ardiradi/PharmaCheck-AI-Core.git
cd PharmaCheck-AI-Core
python -m venv .venv
```

Activate the environment, then install and run the app:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Use Python 3.12 with the pinned dependencies. Configure `AZURE_ENDPOINT` and `AZURE_KEY` as runtime environment variables (preferred for Docker Spaces), or create `.streamlit/secrets.toml` locally:

```toml
AZURE_ENDPOINT = "https://your-resource.cognitiveservices.azure.com/"
AZURE_KEY = "your-key"
```

Do not commit credentials or documents containing confidential information.

Environment values take precedence over the local secrets file. Missing or invalid configuration displays a setup message and stops before the uploader or OCR request. Service failures display a generic message without raw exceptions or credentials. There is no simulated OCR fallback.

Run local configuration, historical mapping, and installed-dependency startup tests:

```bash
python -m unittest discover -s tests -v
```

The current compatibility update pins Streamlit **1.48.1** and sets the Docker WebSocket ping interval and timeout to **30 seconds**, keeping CORS and XSRF protection enabled. Azure AI Form Recognizer, Azure Core, and Pillow pins remain unchanged. See the [compatibility evidence](evidence/runtime-compatibility-2026-10-10.md) for the reason, tests, and live-verification limits.

On 10 October 2026 the updated suite passed on Windows Python 3.12.10: **18 passed, zero skipped**, including all four Streamlit `AppTest` startup cases and two runtime compatibility regressions. `pip check` also passed. The earlier [16-test offline verification](evidence/local-verification-2026-10-10.md) is preserved as a dated record of the previous Streamlit version.

The extraction tests use key-value fixtures rather than real OCR, and the startup tests do not call Azure OCR. These results do not establish Azure accuracy, a successful Linux Docker build, or a recovered live Space. See the [migration handoff](deploy/huggingface/DEPLOY.md) for the exact existing-Space file mapping and pending owner verification.

## Current limitations

- Keyword matching depends on the labels returned by the document model.
- Broad substring keywords, including `ed`, retain the original behavior and can classify unrelated keys; a later extraction redesign needs separate evidence.
- The app does not normalize dates or validate batch formats.
- Extracted values still require a person to verify them against the source document.
- There is no persistent storage or audit trail in this prototype.

## Repository map

```text
app.py             Streamlit interface and extraction workflow
pharmacheck_core.py Environment/secrets resolution and original field mapping
requirements.txt   Pinned Python dependencies
Gambar Test.jpeg   Public synthetic test label
Dockerfile         Proposed Python 3.12 Docker runtime, port 7860
deploy/huggingface/ Existing Space README template and migration handoff
tests/             Local configuration/mapping/startup checks
evidence/          Dated offline verification record
```
