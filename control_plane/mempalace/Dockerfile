FROM python:3.11-slim

WORKDIR /app

# curl is retained for the HEALTHCHECK below; remove it if you switch the
# healthcheck to a pure-python probe.
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/ ./app/

# Non-root runtime user. UID 1000 chosen so volume mounts from the host
# don't end up root-owned. /app is owned by the app user so alembic can
# write its cache files at boot.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin mempalace && \
    chown -R mempalace:mempalace /app
USER mempalace

EXPOSE 8200

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8200/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200"]
