FROM python:3.12-slim

WORKDIR /app

# psycopg2-binary ships its own libpq, so no system deps needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Manifest lives outside the image so it can be edited without rebuilding.
# Compose mounts ../config/maintenance/ to /etc/maintenance/.
ENV MAINTENANCE_MANIFEST=/etc/maintenance/manifest.yaml \
    PYTHONUNBUFFERED=1

COPY . /app/maintenance_router

EXPOSE 9095

CMD ["uvicorn", "maintenance_router.app:app", "--host", "0.0.0.0", "--port", "9095"]
