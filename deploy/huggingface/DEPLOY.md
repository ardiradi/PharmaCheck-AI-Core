# Existing Space migration handoff

Target: [Ard11/PharmaCheck-AI](https://huggingface.co/spaces/Ard11/PharmaCheck-AI), with app URL [ard11-pharmacheck-ai.hf.space](https://ard11-pharmacheck-ai.hf.space/). The previous Docker deployment accepted uploads and previews, while its one Azure extraction failed and the owner reported the resource inactive. This source package makes Tesseract OCR the default and Azure explicitly optional. Native image/PDF OCR has been verified locally on Windows; the new Linux build, live local OCR, and deployed field values remain to be verified. See [local OCR evidence](../../evidence/local-ocr-2026-10-10.md).

On 09 October 2026 the public API reported `sdk: streamlit`, revision `d5a7daa84b77730be3b69f7161277bed6cbe7150`, and `RUNTIME_ERROR` with `Scheduling failure: unable to schedule`. The legacy SDK is deprecated. The remote template Dockerfile points to another entrypoint and is not activated by `sdk: streamlit`. Scheduling is a platform/runtime issue; the proposed migration is not proof that this particular failure is fixed.

On 10 October 2026 the initial Docker revision `51c1edea6fff7366274b57e608326a74c21f92e6` was observed Running, with HTTP 200 at root and a healthy `/_stcore/health`. Two direct browser attempts to upload the public synthetic sample returned HTTP 400 before preview or the extraction button. The build resolved Streamlit 1.32.2 and Tornado 6.5.7. No OCR request had occurred at that point.

The current source pins Streamlit 1.48.1 and adds `--server.websocketPingInterval=30` to the Docker command. The old version's 1-second interval and 30-second requested timeout are reduced to a 1-second effective timeout by modern Tornado; the updated configuration retains 30 seconds. This removes a reproduced compatibility defect, but the uninspected live HTTP 400 response reason prevents treating it as the proven upload root cause. CORS and XSRF defaults stay enabled. See [compatibility evidence](../../evidence/runtime-compatibility-2026-10-10.md).

The updated Docker revision `f976fd01e39da75fc46a3dc6937d316d981749e6` reached Running and accepted the public sample, showing its preview and extraction button. One live extraction action failed with the safe generic message; the actual HTTP status and SDK error code were not captured. On 10 October the owner confirmed that the Azure Document Intelligence resource is inactive. No three-field result, restored OCR service, or accuracy measurement follows from the successful upload. [The follow-up record](../../evidence/ocr-diagnostics-2026-10-10.md) describes the sanitized diagnostics and offline tests.

## Reviewed file mapping

| Source repository file | Existing Space repository destination |
| --- | --- |
| `deploy/huggingface/README.md` | `README.md` at Space root |
| `Dockerfile` | `Dockerfile` at Space root |
| `.dockerignore` | `.dockerignore` at Space root |
| `requirements.txt` | `requirements.txt` at Space root |
| `app.py` | `app.py` at Space root |
| `pharmacheck_core.py` | `pharmacheck_core.py` at Space root |

Do not mirror the source repository's main README over the Space metadata. `sdk: docker` and `app_port: 7860` must be in the Space root README. The Docker command runs the actual `app.py` entrypoint, binds to `0.0.0.0:7860`, and runs as user UID 1000. The build context includes only runtime files. The original source history and `Gambar Test.jpeg` remain in GitHub; uploads, secrets, and local virtual environments are excluded.

## Owner execution

1. Confirm the reviewed source changes are published to GitHub before deployment. Save the existing Space revision and use a normal clone/commit/push that preserves its history; no force push or new Space is required.
2. Sign in as an owner with write access to `Ard11/PharmaCheck-AI`. Use the provider's secret settings or authenticated Git credential flow; never paste a write token or Azure key into a public file or chat.
3. Copy only the six reviewed deployment files above. Inspect the diff, including the root README SDK change, before committing to the existing Space.
4. Keep the existing free CPU hardware. Default local OCR requires no Azure secret or paid API. The Docker build installs the native runtime and verifies the pinned official English model. Do not change Azure secrets, activate the inactive resource, create an account, or change billing. Azure remains an explicitly selected optional route; no automatic fallback or additional genuine Azure action is included.
5. Wait for build and runtime logs. Record the actual deployed revision, build result, runtime stage, and any sanitized error. If scheduling still fails, use the owner's restart controls and platform support path; do not claim that code changes resolved infrastructure scheduling.
6. Check HTTP `/` and `/_stcore/health`, then inspect the real app UI. The default local mode must reach the uploader without Azure configuration. Use the public synthetic label for local OCR and record actual raw text/candidate fields; compare against the source without claiming general accuracy. Test a bounded PDF separately if authorized. Do not select Azure or count fixture tests as deployed OCR success.
7. Only after the runtime and real workflow succeed, update the portfolio's dated Space-error note using the new evidence.

## Local verification commands

Python 3.12 is the locally available interpreter. Streamlit remains 1.48.1; Azure/Pillow direct pins retain their original versions. New pins are `tesserocr==2.10.0` and `pypdfium2==5.14.0`. Windows uses the project's linked self-contained native wheel; Linux uses the PyPI manylinux wheel and distribution runtime packages. Record the actual Linux Tesseract version independently: the probed Windows engine is 5.5.2. Both use the pinned English model downloaded by the Dockerfile with a SHA-256 assertion. `python:3.12-slim` is a minor-version tag, not a verified immutable digest. Windows tests do not establish that the new Linux image builds.

The earlier diagnostics revision passed all 23 tests with no skips on Windows Python 3.12.10, Streamlit 1.48.1, and Tornado 6.5.10. Its fake Azure workflows exposed no fixture secrets and made no genuine OCR call. That dated [diagnostics record](../../evidence/ocr-diagnostics-2026-10-10.md) remains intact. The replacement's actual native image/PDF and local UI checks are recorded separately in [local OCR evidence](../../evidence/local-ocr-2026-10-10.md).

Historical preparation on 09 October had twelve configuration/mapping tests pass and four startup tests skip because dependencies were incomplete. The earlier 10 October [16-test result](../../evidence/local-verification-2026-10-10.md) and [18-test result](../../evidence/runtime-compatibility-2026-10-10.md) remain intact. Local Docker CLI was available but its Linux daemon was not running. Hugging Face built the previous compatibility image and accepted its upload/preview; that is not evidence for the new offline OCR image.

```powershell
py -3.12 -m venv .venv-recovery
# On Windows install the matching project-recommended tesserocr wheel first,
# then set PHARMACHECK_TESSDATA to the pinned English-model directory.
.\.venv-recovery\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-recovery\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-recovery\Scripts\python.exe -m pip check
```

When a functioning Docker daemon is available:

```powershell
docker build -t pharmacheck-recovery .
docker run --rm -p 7860:7860 pharmacheck-recovery
```

The container without Azure credentials should show the local uploader and perform local OCR within its limits. Rendered PDFs are limited to five pages, 12 megapixels per page at 300 DPI, with 15 seconds per OCR page and a 60-second total worker deadline. PDFium and Tesseract live in an isolated worker; native objects and temporary files are closed/removed. Missing and conflicting field candidates require human review.

## Primary references

- [Hugging Face Streamlit SDK deprecation](https://huggingface.co/docs/hub/spaces-sdks-streamlit)
- [Hugging Face Docker Spaces: metadata, runtime secrets, and UID 1000](https://huggingface.co/docs/hub/spaces-sdks-docker)
- [Space README configuration reference](https://huggingface.co/docs/hub/spaces-config-reference)
- [Streamlit secrets API](https://docs.streamlit.io/develop/api-reference/connections/st.secrets)
- [Tesseract input formats: PDF requires rasterization](https://tesseract-ocr.github.io/tessdoc/InputFormats.html)
- [tesserocr native binding and Windows installation](https://github.com/sirfz/tesserocr)
- [pypdfium2 native API and concurrency constraints](https://pypdfium2.readthedocs.io/en/stable/python_api.html)
