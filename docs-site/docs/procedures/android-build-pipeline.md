# Android build pipeline

Android builds run in a dedicated builder image. The general Dev Workspace
`sandbox` intentionally does not contain Java, Gradle, or the Android SDK.

## Build image

Build the profile-gated image on Lovelace:

```bash
docker compose --profile android -f execution_plane/docker-compose.yml build android-builder
```

The service is not started as a resident workload. The backend creates a
disposable builder for each authenticated build request and applies these
limits:

- 8 GB memory
- 4 CPUs
- 512 processes
- 1 GB temporary filesystem
- 15-minute wall-clock timeout
- 500 MB source transfer and 100 MB APK limits

## API contract

`POST /v1/dev/android/build` accepts `{ "project_id": "..." }`. The project
must belong to the authenticated user. The source is copied from the existing
dev sandbox into the disposable builder; only the resulting APK is copied to
`/workspace/delivered_artifacts`.

The response contains a signed, 24-hour `download_url`. The build refuses to
start unless `ARTIFACT_SIGNING_SECRET` (or the existing
`FRIDAY_IMAGE_SIGNING_SECRET` compatibility fallback) is configured. APK
downloads use the existing HMAC-verified `/v1/public-artifacts/{filename}`
route and are returned as attachments.

The first controlled deployment should build the image and run one small
authenticated Android fixture through the endpoint. Do not add the SDK to
`Dockerfile.dev-sandbox` or enable the `android` Compose profile during normal
startup.
