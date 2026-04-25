const CACHE_NAME = "hive-mind-v2";
const OFFLINE_URL = "/offline";

const PRECACHE_ASSETS = [
  "/offline",
  // manifest.json is excluded — it is fetched behind Authentik and will be
  // redirected to auth.shivelymedia.com during install, causing a CORS error.
];

// Install: cache offline fallback
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Fetch strategy
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== "GET") return;

  // API calls: network-only (never cache stale chat data)
  if (url.pathname.startsWith("/api/")) return;

  // Skip Authentik-proxied paths — these redirect to auth.shivelymedia.com
  // (a private-network host), causing CORS / Private Network Access errors
  // if the service worker intercepts them. Let the browser handle them directly.
  if (
    url.pathname === "/manifest.json" ||
    url.pathname.startsWith("/outpost.goauthentik.io/")
  ) return;

  // Static assets (_next/static): cache-first
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        cache.match(request).then((cached) => {
          if (cached) return cached;
          return fetch(request).then((response) => {
            if (response.ok) {
              cache.put(request, response.clone());
            }
            return response;
          });
        })
      )
    );
    return;
  }

  // HTML pages: network-first with offline fallback
  if (request.headers.get("accept")?.includes("text/html")) {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  // Other assets (fonts, images): stale-while-revalidate
  // Guard: if the response was redirected to a different origin (e.g. Authentik
  // OAuth), do NOT cache it and let the browser handle it natively so CORS
  // policy doesn't block the service worker's opaque fetch.
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(request).then((cached) => {
        const requestOrigin = new URL(request.url).origin;
        const fetched = fetch(request).then((response) => {
          // If redirected cross-origin (e.g. to Authentik), skip caching and
          // return the cached version (if any) or a simple network error so
          // the browser can handle auth normally.
          if (response.redirected && new URL(response.url).origin !== requestOrigin) {
            return cached || Response.error();
          }
          if (response.ok) {
            cache.put(request, response.clone());
          }
          return response;
        }).catch(() => cached || Response.error());
        return cached || fetched;
      })
    )
  );
});
