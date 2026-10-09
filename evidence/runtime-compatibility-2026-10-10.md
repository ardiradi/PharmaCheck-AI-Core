# Streamlit runtime compatibility — 10 October 2026

The source now pins **Streamlit 1.48.1** and the Docker command sets `server.websocketPingInterval=30`. The actual CLI configuration produces interval **30 seconds**, requested timeout **30 seconds**, and effective Tornado timeout **30 seconds**. CORS and XSRF defaults remain enabled. Azure AI Form Recognizer 3.3.3, Azure Core 1.30.1, Pillow 10.2.0, application code, and extraction behavior are unchanged.

## Trigger and limits of the diagnosis

The initial Docker Space revision `51c1edea6fff7366274b57e608326a74c21f92e6` reached Running with root HTTP 200 and a healthy `/_stcore/health`; these observations were verified at 00:55–00:56 WIB. Its build resolved Streamlit 1.32.2 and Tornado 6.5.7. Two direct browser uploads of the public synthetic label failed with HTTP 400 before preview, an extraction button, or any OCR request.

The local old stack, Streamlit 1.32.2 and Tornado 6.5.10, reproduces a timing mismatch: its 1-second interval and 30-second requested timeout become a **1-second effective timeout**. Disconnected sessions can then be rejected by Streamlit's upload handler. The failing live response reason was not inspected, so this is a plausible mechanism rather than a proven HTTP 400 root cause.

## Version choice

[Streamlit's 2025 release notes](https://docs.streamlit.io/develop/quick-reference/release-notes/2025) identify the timing fix in 1.47.0 and the supported ping setting in 1.48.0. [PyPI lists 1.48.1](https://pypi.org/project/streamlit/1.48.1/) as the patch release used here. This narrow upgrade retains the Tornado server and the existing image API. The latest stable checked during this work was 1.65.0; it uses a different Starlette/Uvicorn server stack, so that broader migration was left outside this compatibility change.

No CORS/XSRF disabling, Tornado downgrade, or internal runtime monkey patch is used.

## Verification

On Windows Python **3.12.10**, Streamlit **1.48.1**, and Tornado **6.5.10**, the complete suite passed **18 tests, zero skips, zero failures or errors**. `pip check` found no broken requirements.

- Twelve configuration/mapping tests and all four real Streamlit `AppTest` startup cases pass.
- The Docker CLI regression parses the actual command, stops before server startup, and confirms the supported flag reaches the real Streamlit config and Tornado's effective timeout. Enabled CORS/XSRF defaults are also checked.
- The default-settings regression confirms modern Tornado retains 30 seconds with the updated Streamlit defaults, while the legacy 1/30 pair still clamps to 1 second as a negative control.
- Startup fixtures preserve OS variables, inject dummy secrets, prevent secret-file reads and socket connections, and verify that no OCR call occurs.

The first upgrade run had one AppTest timeout because its old fixture removed the OS home variables before lazy config initialization. That fixture was corrected; this was a test setup failure, not an observed production app failure. Protobuf deprecation and bare-mode ScriptRunContext warnings remain non-failing on Python 3.12.10.

The [earlier 16-test record](local-verification-2026-10-10.md) is preserved. The updated Linux image, genuine browser upload, and one authorized OCR request require separate live verification. This source publication does not establish a recovered extraction workflow or OCR accuracy.
