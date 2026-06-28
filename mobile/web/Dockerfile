# Memex mobile web app — serves the prebuilt Memex Desktop SPA + reverse proxy.
# The SPA is built from the memex-desktop repo (`npx vite build`) and copied into
# ./spa before building this image (see README). Kept out of git (build artifact).
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY spa/       /usr/share/nginx/html/

EXPOSE 3000
