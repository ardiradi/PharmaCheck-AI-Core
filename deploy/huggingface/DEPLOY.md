# Existing Space migration handoff

Target: [Ard11/PharmaCheck-AI](https://huggingface.co/spaces/Ard11/PharmaCheck-AI), with app URL [ard11-pharmacheck-ai.hf.space](https://ard11-pharmacheck-ai.hf.space/). The initial Docker migration reached Running, but its sample upload failed before OCR. This handoff now includes a tested compatibility update; a recovered extraction workflow remains unverified.

On 09 October 2026 the public API reported `sdk: streamlit`, revision `d5a7daa84b77730be3b69f7161277bed6cbe7150`, and `RUNTIME_ERROR` with `Scheduling failure: unable to schedule`. The legacy SDK is deprecated. The remote template Dockerfile points to another entrypoint and is not activated by `sdk: streamlit`. Scheduling is a platform/runtime issue; the proposed migration is not proof that this particular failure is fixed.

On 10 October 2026 the initial Docker revision `51c1edea6fff7366274b57e608326a74c21f92e6` was observed Running, with HTTP 200 at root and a healthy `/_stcore/health`. Two direct browser attempts to upload the public synthetic sample returned HTTP 400 before preview or the extraction button. The build resolved Streamlit 1.32.2 and Tornado 6.5.7. No OCR request had occurred at that point.

The current source pins Streamlit 1.48.1 and adds `--server.websocketPingInterval=30` to the Docker command. The old version's 1-second interval and 30-second requested timeout are reduced to a 1-second effective timeout by modern Tornado; the updated configuration retains 30 seconds. This removes a reproduced compatibility defect, but the uninspected live HTTP 400 response reason prevents treating it as the proven upload root cause. CORS and XSRF defaults stay enabled. See [compatibility evidence](../../evidence/runtime-compatibility-2026-10-10.md).

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
4. Confirm both runtime secret names `AZURE_ENDPOINT` and `AZURE_KEY` in Settings → Secrets. Azure credentials must be real and authorized. Do not request paid hardware or change visibility/billing for this migration.
5. Wait for build and runtime logs. Record the actual deployed revision, build result, runtime stage, and any sanitized error. If scheduling still fails, use the owner's restart controls and platform support path; do not claim that code changes resolved infrastructure scheduling.
6. Check HTTP `/` and `/_stcore/health`, then inspect the real app UI. Without Azure configuration, expect a setup message and no upload/extraction result. With real authorized Azure configuration, use the public synthetic label for a single genuine extraction and compare the three displayed fields to the document. Do not count a helper fixture test as OCR success.
7. Only after the runtime and real workflow succeed, update the portfolio's dated Space-error note using the new evidence.

## Local verification commands

Python 3.12 is the locally available interpreter. Streamlit is now pinned to 1.48.1; the three Azure/Pillow direct pins retain their original versions. `python:3.12-slim` is a Docker minor-version tag, not a verified immutable digest. A local Windows Python test does not establish that an updated Linux image builds.

The current compatibility verification used Windows Python 3.12.10, Streamlit 1.48.1, and Tornado 6.5.10: **all 18 tests passed, zero skipped**, including all four Streamlit `AppTest` startup tests and two runtime compatibility regressions. `pip check` reported no broken requirements. The CLI regression parses the actual Docker command without starting a server and checks the effective 30-second timeout plus enabled protections. Startup fixtures preserve OS environment variables while isolating secrets and blocking network access. See the [compatibility record](../../evidence/runtime-compatibility-2026-10-10.md). This verifies local contracts; it does not verify the updated Linux container or real Azure OCR.

Historical preparation on 09 October had twelve configuration/mapping tests pass and four startup tests skip because dependencies were incomplete. The earlier 10 October [16-test result](../../evidence/local-verification-2026-10-10.md) established startup on Streamlit 1.32.2; this 18-test result supersedes it for the compatibility update. Local Docker CLI was available but its Linux daemon was not running. The initial image has built on Hugging Face; the updated image, upload, and real OCR checks remain pending.

```powershell
py -3.12 -m venv .venv-recovery
.\.venv-recovery\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-recovery\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-recovery\Scripts\python.exe -m pip check
```

When a functioning Docker daemon is available:

```powershell
docker build -t pharmacheck-recovery .
docker run --rm -p 7860:7860 pharmacheck-recovery
```

The container without credentials should show a setup message. Set real secrets through an approved runtime secret mechanism for an actual OCR test; never add them to the Dockerfile or image layers.

## Primary references

- [Hugging Face Streamlit SDK deprecation](https://huggingface.co/docs/hub/spaces-sdks-streamlit)
- [Hugging Face Docker Spaces: metadata, runtime secrets, and UID 1000](https://huggingface.co/docs/hub/spaces-sdks-docker)
- [Space README configuration reference](https://huggingface.co/docs/hub/spaces-config-reference)
- [Streamlit secrets API](https://docs.streamlit.io/develop/api-reference/connections/st.secrets)
