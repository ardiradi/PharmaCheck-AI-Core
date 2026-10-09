# Offline verification — 10 October 2026

The complete unittest suite passed: **16 tests, zero skips, zero failures or errors**, in **9.094 seconds**. All four Streamlit `AppTest` startup tests ran. `pip check` completed successfully with `No broken requirements found.`

The tested application and tests were from source commit `0f037582e605a339d965d83ff82926877fe713d7`. This later documentation update does not change runtime code, tests, or dependency versions.

## Environment

- Windows, Python **3.12.10**, isolated project virtual environment.
- Direct project pins: Streamlit **1.32.2**, Azure AI Form Recognizer **3.3.3**, Azure Core **1.30.1**, Pillow **10.2.0**.
- Dependencies installed from official PyPI using binary wheels. No global package installation.
- Verification completed at **00:36:34 WIB on 10 October** (**17:36:34 UTC on 9 October**).

## Checks performed

```text
python -m unittest discover -s tests -v
python -m pip check
```

Four real Streamlit `AppTest` executions verified that missing configuration displays setup instructions, invalid configuration avoids disclosing raw values, configured startup exposes the uploader without invoking OCR, and client initialization failure displays a safe error. The configured startup test mocks `begin_analyze_document` with a failure if called and confirms that it is never called.

The remaining twelve tests cover configuration precedence and errors, plus original field mapping behavior with synthetic key-value fixtures. The known broad `ed` substring collision remains unchanged and is covered as historical behavior.

Two Protobuf deprecation warnings concerning future Python 3.14 behavior appeared during import; they did not fail the tests on Python 3.12.10.

## Limits

The 9 October result of twelve passing tests and four skipped startup tests is superseded for this local environment. These tests establish local startup and the stated contracts. They do not establish OCR accuracy or the validity of any extracted pharmaceutical document.

No real Azure OCR request or credential was used. The Linux Docker image has not been built or run; the Docker daemon was not started. No Hugging Face deployment or recovery of the public runtime occurred as part of this verification. Those checks remain separate owner steps in the [migration handoff](../deploy/huggingface/DEPLOY.md).
