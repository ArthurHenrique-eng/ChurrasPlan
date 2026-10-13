import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const config = readFileSync("FrontEnd/js/config.js", "utf8");
const sw = readFileSync("FrontEnd/sw.js", "utf8");

function apiBase(hostname, port, override = "") {
  const window = { location: { protocol: "http:", hostname, port }, CHURRASPLAN_CONFIG: override ? { apiBaseUrl: override } : undefined };
  const document = { querySelector: () => null };
  return vm.runInNewContext(config + "\nAPI_BASE_URL;", { window, document });
}

// Docker proxy serves API and frontend from the same origin.
assert.equal(apiBase("localhost", "8080"), "");
assert.equal(apiBase("127.0.0.1", "8080"), "");
assert.equal(apiBase("localhost", ""), "");
// Live Server E2E serves the frontend separately from the API.
assert.equal(apiBase("localhost", "5500"), "http://localhost:8000");
assert.equal(apiBase("127.0.0.1", "5501"), "http://127.0.0.1:8000");
assert.equal(apiBase("site.example", ""), "");
assert.equal(apiBase("localhost", "8080", "http://localhost:9000/"), "http://localhost:9000");

const listeners = new Map();
const requested = [];
const configUrl = "http://localhost:8080/js/config.js";
const oldResponse = new Response("const API_BASE_URL = 'http://localhost:8000';");
const saved = new Map();
const caches = {
  match: async (request) => saved.get(request.url) || oldResponse.clone(),
  open: async () => ({
    put: async (request, response) => { saved.set(request.url, response.clone()); },
  }),
};
const self = {
  location: { origin: "http://localhost:8080" },
  addEventListener: (event, handler) => listeners.set(event, handler),
};
const fetch = async (request, options) => {
  requested.push({ url: request.url, options });
  return new Response("const API_BASE_URL = '';", { status: 200 });
};
vm.runInNewContext(sw, { self, caches, fetch, URL, Response });

const handler = listeners.get("fetch");
assert.equal(typeof handler, "function");
const req = { url: configUrl, method: "GET", mode: "cors" };
let promise;
handler({ request: req, respondWith: (pending) => { promise = pending; } });
assert.ok(promise, "service worker must intercept application scripts");
const latest = await promise;
assert.equal(await latest.text(), "const API_BASE_URL = '';", "never return stale config when network works");
assert.equal(requested.length, 1, "scripts must check the network");
assert.equal(requested[0].options.cache, "no-store", "browser HTTP cache must not preserve old JS");
assert.equal(await saved.get(configUrl).text(), "const API_BASE_URL = '';", "fresh response replaces stale SW cache");

let intercepted = false;
handler({
  request: { url: "http://localhost:8080/api/auth/register", method: "GET", mode: "cors" },
  respondWith: () => { intercepted = true; },
});
assert.equal(intercepted, false, "API requests must bypass the service worker");

console.log("Docker origin, Live Server origin, PWA refresh and API bypass OK");
