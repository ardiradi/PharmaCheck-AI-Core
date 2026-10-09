---
title: PharmaCheck AI
emoji: 💊
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
short_description: Local OCR candidates for labels and documents
pinned: false
---

# PharmaCheck AI

This Streamlit prototype uses Tesseract OCR on the application server by default, without an Azure account or API key. It accepts JPG/PNG and bounded PDFs, shows candidate batch numbers, expiry dates, and material names, and preserves raw OCR for human review. It does not make medical, release, or quality decisions. OCR can misread text, including dosage; always check the source.

Source: [PharmaCheck-AI-Core](https://github.com/ardiradi/PharmaCheck-AI-Core).

Local processing is limited to 10 MiB, five PDF pages, 12 megapixels per page, and a 60-second worker deadline. Missing and conflicting fields are explicit; no identifier or date is silently corrected. Temporary document files are cleaned up; there is no document database.

Azure Document Intelligence remains an explicitly selected optional route. Only that route requires an active resource and `AZURE_ENDPOINT`/`AZURE_KEY` in Space Settings → Secrets. Local failures never automatically contact Azure. The owner reported the previous resource inactive on 10 October 2026.
