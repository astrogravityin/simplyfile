# Self-host image (W1.4, scorecard B10). The portal's memory lives in the /data volume, never in the image.
#   docker build -t simplyfile .            (or: docker compose up -d --build)
#   docker run -d -p 8830:8830 -v sf-data:/data simplyfile
# Values come from env (PORTAL_*), set in compose.yml or `docker run -e`; nothing site-specific is baked in.
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PORTAL_DATA=/data TV_DATA=/data PORT=8830
# git: About us and /health/run name the running commit (git log in /app)
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --create-home --home-dir /home/portal --uid 10001 portal \
 && mkdir -p /data && chown portal:portal /data

WORKDIR /app
# packages first (cached layer): the lock file when there is one, else requirements.txt
COPY requirements*.txt requirements*.lock* ./
RUN if [ -f requirements.lock ]; then pip install -r requirements.lock; else pip install -r requirements.txt; fi
COPY --chown=portal:portal . .
RUN git config --system --add safe.directory /app

USER portal
VOLUME ["/data"]
EXPOSE 8830
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8830'), timeout=4)" || exit 1
CMD ["sh", "-c", "exec python -m uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
