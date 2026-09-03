# PharmaCheck AI

PharmaCheck AI is a Streamlit prototype for extracting important fields from pharmaceutical labels and documents with Azure AI Document Intelligence.

[Open the live demo](https://ard11-pharmacheck-ai.hf.space/)

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

The field mapping is intentionally transparent: `app.py` contains the keyword lists and matching logic used to classify extracted keys.

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

Create `.streamlit/secrets.toml` locally:

```toml
AZURE_ENDPOINT = "https://your-resource.cognitiveservices.azure.com/"
AZURE_KEY = "your-key"
```

Do not commit credentials or documents containing confidential information.

## Current limitations

- Keyword matching depends on the labels returned by the document model.
- The app does not normalize dates or validate batch formats.
- Extracted values still require a person to verify them against the source document.
- There is no persistent storage or audit trail in this prototype.

## Repository map

```text
app.py             Streamlit interface and extraction workflow
requirements.txt   Pinned Python dependencies
Gambar Test.jpeg   Public synthetic test label
```
