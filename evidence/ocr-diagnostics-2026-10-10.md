# Preview and safe OCR diagnostics — 10 October 2026

Docker revision `f976fd01e39da75fc46a3dc6937d316d981749e6` reached Running with Streamlit 1.48.1. The public 2,198,306-byte sample uploaded successfully and displayed a preview plus the extraction button. One live extraction action then failed with the existing safe generic error. Its HTTP status and SDK code were not captured. The owner confirmed on 10 October that the Azure Document Intelligence resource is inactive.

Docker and upload/preview are verified. Genuine OCR output, the three extracted fields, and general accuracy remain unverified. The timing mismatch was reproduced locally and upload worked after the compatibility change; the exact earlier HTTP 400 cause remains inferred.

## Refinement

- Replace the deprecated preview argument with `use_container_width=True` for the pinned Streamlit 1.48.1.
- Log only a fixed allowlisted exception label, a validated integer HTTP status, and an exact allowlisted SDK code. Unknown metadata is omitted. Exception text, stack traces, response bodies/headers, request URLs, endpoints, keys, and document content are never included.
- Show plain next steps only from a known validated HTTP status. Unknown status keeps the existing generic message. Classification does not infer an expired key or a specific cause from exception text.

[Azure's SDK reference](https://learn.microsoft.com/en-us/python/api/azure-core/azure.core.exceptions.httpresponseerror) describes the structured status and error fields; [the Document Intelligence error guide](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/how-to-guides/resolve-errors?view=doc-intel-4.0.0) supplies the fixed top-level code labels used here. Arbitrary code strings are not safe log content and are rejected.

## Offline verification

The complete suite passed **23 tests, zero skips, zero failures or errors** on Windows Python 3.12.10, Streamlit 1.48.1, and Tornado 6.5.10. `pip check` passed. Three new unit cases exercise known and unsafe metadata, and two real AppTest flows render the uploader and actual PNG preview, click the actual app button, and inject fake poller failures.

Each fake flow makes one client call and one poller call, displays safe failure feedback without success output, produces one sanitized log record without traceback, and exposes no fixture secret in textual UI or logs. Guards assert zero secret-file reads, socket connections, or response-body reads. No preview deprecation warning is shown. The supplied file value is mocked, so these tests do not establish browser HTTP-upload behavior or OCR accuracy.

Streamlit 1.48.1, the 30-second ping setting, Azure/Pillow pins, original model selection, and field-mapping behavior remain unchanged. Prior source/runtime/verification records are preserved. This refinement does not activate Azure, create an account, alter billing, or perform another real OCR action; subsequent live checks can inspect the preview without invoking extraction.
