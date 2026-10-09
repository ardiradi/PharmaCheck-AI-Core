# Existing Space migration handoff

Target: [Ard11/PharmaCheck-AI](https://huggingface.co/spaces/Ard11/PharmaCheck-AI), with app URL [ard11-pharmacheck-ai.hf.space](https://ard11-pharmacheck-ai.hf.space/). This is a preparation package, not a recovered live deployment.

On 09 October 2026 the public API reported `sdk: streamlit`, revision `d5a7daa84b77730be3b69f7161277bed6cbe7150`, and `RUNTIME_ERROR` with `Scheduling failure: unable to schedule`. The legacy SDK is deprecated. The remote template Dockerfile points to another entrypoint and is not activated by `sdk: streamlit`. Scheduling is a platform/runtime issue; the proposed migration is not proof that this particular failure is fixed.

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

Python 3.12 is the locally available interpreter. The four direct dependencies remain pinned to the project's original versions; `python:3.12-slim` is a Docker minor-version tag, not a verified immutable digest. A local Windows Python test does not establish that the Linux image builds.

Preparation checks on 09 October used Windows Python 3.12.10: twelve configuration/mapping tests passed, while four installed-dependency Streamlit startup tests were skipped. The optional dependency install was stopped after a slow PyArrow wheel download; full dependency compatibility and Streamlit startup remain unverified. Complete the install and rerun the entire suite before deployment. Docker CLI was available but its Linux daemon was not running, so no image build was performed.

```powershell
py -3.12 -m venv .venv-recovery
.\.venv-recovery\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-recovery\Scripts\python.exe -m unittest discover -s tests -v
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
