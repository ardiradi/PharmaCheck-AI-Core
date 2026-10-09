---
title: PharmaCheck AI
emoji: 💊
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
short_description: Document field extraction prototype using Azure
pinned: false
---

# PharmaCheck AI

This Streamlit prototype sends uploaded document bytes to Azure Document Intelligence's `prebuilt-document` model and maps returned fields to batch number, expiry date, and material name. The output requires human verification; it does not make medical, release, or quality decisions.

Source: [PharmaCheck-AI-Core](https://github.com/ardiradi/PharmaCheck-AI-Core).

The owner must configure `AZURE_ENDPOINT` and `AZURE_KEY` in this Space's Settings → Secrets. Missing configuration displays a setup message; there is no simulated OCR fallback. Credentials are not part of the repository or Docker image.
