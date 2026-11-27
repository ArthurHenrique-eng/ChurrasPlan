const VERSION = "churrasplan-v7.0.0";
const STATIC_CACHE = `${VERSION}-static`;
const PAGE_CACHE = `${VERSION}-pages`;
// Tudo o que as páginas de SAFE_PAGES precisam para abrir sem rede.
// scripts/validate_frontend.py confere se cada arquivo existe: um único
// caminho quebrado faz cache.addAll falhar e o service worker não instala.
const STATIC_ASSETS = [
  "/offline.html",
  "/favicon.svg",
  "/manifest.webmanifest",
  "/assets/logo-icon-96.webp",
  "/assets/logo-wordmark-320.webp",
  "/assets/pwa/icon-192.png",
  "/assets/pwa/icon-512.png",
  "/fonts/archivo-latin-var.woff2",
  "/css/ds.css",
  "/css/pages/home.css",
  "/css/pages/planner.css",
  "/css/pages/content.css",
  "/js/config.js",
  "/js/state.js",
  "/js/api.js",
  "/js/script.js",
  "/js/icons.js",
  "/js/ui.js",
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
function isApplicationCode(requestUrl) { return /\.(?:js|css)$/.test(requestUrl.pathname); }

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
      // Scripts e estilos precisam acompanhar cada deploy. Cache-first mantinha
      // config.js antigo (API :8000), quebrando autenticação no Docker :8080.
      // force-cache nunca deve ser usado para o código da aplicação.
      if (isApplicationCode(url)) {
        try {
          const fresh = await fetch(request, { cache: "no-store" });
          if (fresh.ok) {
            (await caches.open(STATIC_CACHE)).put(request, fresh.clone());
            return fresh;
          }
        } catch { /* offline: reutiliza o último código disponível */ }
        return (await caches.match(request)) || new Response("", { status: 504 });
      }
      const cached = await caches.match(request);
      if (cached) return cached;
      try {
        const fresh = await fetch(request);
        if (fresh.ok) (await caches.open(STATIC_CACHE)).put(request, fresh.clone());
        return fresh;
      } catch { return new Response("", { status: 504 }); }
    })());
  }
});
