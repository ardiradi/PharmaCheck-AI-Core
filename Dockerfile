FROM python:3.12-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 user
USER user
WORKDIR /home/user/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/home/user/.local/bin:$PATH

COPY --chown=user:user requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --only-binary=tesserocr,pypdfium2 --user -r requirements.txt \
    && python -c "import tesserocr; print(tesserocr.tesseract_version())"
COPY --chown=user:user app.py pharmacheck_core.py ./
RUN python -c "import hashlib, pathlib, urllib.request; data=urllib.request.urlopen('https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/eng.traineddata', timeout=30).read(); assert hashlib.sha256(data).hexdigest() == '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2', 'English model checksum mismatch'; pathlib.Path('tessdata').mkdir(); pathlib.Path('tessdata/eng.traineddata').write_bytes(data)"
ENV PHARMACHECK_TESSDATA=/home/user/app/tessdata

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/_stcore/health', timeout=4)" || exit 1

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=7860", "--server.headless=true", "--server.websocketPingInterval=30", "--server.maxUploadSize=10", "--browser.gatherUsageStats=false"]
