FROM python:3.12-slim

RUN useradd --create-home --uid 1000 user
USER user
WORKDIR /home/user/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/home/user/.local/bin:$PATH

COPY --chown=user:user requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --user -r requirements.txt
COPY --chown=user:user app.py pharmacheck_core.py ./

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/_stcore/health', timeout=4)" || exit 1

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=7860", "--server.headless=true", "--browser.gatherUsageStats=false"]
