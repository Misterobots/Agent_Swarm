FROM python:3.12-slim AS builder

WORKDIR /docs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdocs build --strict

FROM nginx:alpine
COPY --from=builder /docs/site /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
