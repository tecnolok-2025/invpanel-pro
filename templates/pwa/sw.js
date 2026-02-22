/* InvPanel Service Worker (v2)
   - Keep it minimal for iOS Safari compatibility.
   - Bump CACHE_NAME when you change assets to force refresh.
*/

const CACHE_NAME = "invpanel-v2";
const URLS_TO_CACHE = [
  "/",
  "/login/",
  "/static/css/base.css",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(URLS_TO_CACHE))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Network-first for HTML (avoid stale templates after deploy)
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/"))
    );
    return;
  }

  // Cache-first for static assets
  event.respondWith(
    caches.match(event.request).then((response) => response || fetch(event.request))
  );
});
