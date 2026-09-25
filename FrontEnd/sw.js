const VERSION = "churrasplan-v6.5.1";
const STATIC_CACHE = `${VERSION}-static`;
const PAGE_CACHE = `${VERSION}-pages`;
const STATIC_ASSETS = [
  "/offline.html",
  "/favicon.svg",
  "/manifest.webmanifest",
  "/assets/logo-icon.png",
  "/assets/logo-wordmark.png",
  "/assets/pwa/icon-192.png",
  "/assets/pwa/icon-512.png",
  "/css/unified-core.css",
  "/css/unified-home.css",
  "/css/integracao-v3.css",
  "/css/production-v63.css",
  "/js/config.js",
  "/js/state.js",
  "/js/api.js",
  "/js/script.js",
  "/js/icons.js",
  "/js/pwa.js"
];
const SAFE_PAGES = new Set([
  "/", "/index.html", "/planejamento.html", "/carnes.html", "/bebidas.html", "/extras.html",
  "/privacidade.html", "/termos.html", "/cookies.html", "/offline.html"
]);

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith("churrasplan-") && ![STATIC_CACHE, PAGE_CACHE].includes(key)).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

function isApi(requestUrl) { return requestUrl.pathname.startsWith("/api/"); }
function isStatic(requestUrl) { return /\.(?:css|js|png|jpg|jpeg|svg|webp|woff2?|webmanifest)$/.test(requestUrl.pathname); }

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || isApi(url)) return;

  if (request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (response.ok && SAFE_PAGES.has(url.pathname)) {
          const cache = await caches.open(PAGE_CACHE);
          cache.put(request, response.clone());
        }
        return response;
      } catch {
        const cached = SAFE_PAGES.has(url.pathname) ? await caches.match(request) : null;
        return cached || await caches.match("/offline.html");
      }
    })());
    return;
  }

  if (isStatic(url)) {
    event.respondWith((async () => {
      const cached = await caches.match(request);
      const network = fetch(request).then(async (response) => {
        if (response.ok) (await caches.open(STATIC_CACHE)).put(request, response.clone());
        return response;
      }).catch(() => null);
      return cached || await network || new Response("", { status: 504 });
    })());
  }
});
