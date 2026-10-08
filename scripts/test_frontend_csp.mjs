import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const nginx = readFileSync("FrontEnd/nginx.conf", "utf8");
const html = readFileSync("FrontEnd/onde-comprar.html", "utf8");
const readme = readFileSync("README.md", "utf8");

const match = nginx.match(/add_header Content-Security-Policy "([^"]+)" always;/);
assert.ok(match, "Política CSP deve estar presente no Nginx");
const policy = match[1];
const directive = (name) => policy.split(";").map((x) => x.trim()).find((x) => x.startsWith(name + " "));
for (const key of ["default-src", "script-src", "style-src", "img-src", "connect-src", "worker-src", "frame-ancestors", "object-src"]) {
    assert.ok(directive(key), "Diretiva de segurança ausente: " + key);
}
assert.match(directive("script-src"), /https:\/\/cdn\.jsdelivr\.net/);
assert.match(directive("style-src"), /https:\/\/cdn\.jsdelivr\.net/);
assert.match(directive("worker-src"), /blob:/, "MapLibre requer worker blob:");
assert.equal(directive("connect-src"), "connect-src 'self'", "Geoapify deve operar pelo backend");
assert.equal(directive("object-src"), "object-src 'none'");
assert.equal(directive("frame-ancestors"), "frame-ancestors 'none'");
assert.doesNotMatch(policy, /(?:maps|places)\.googleapis\.com|maps\.gstatic\.com|googleusercontent\.com/, "remover permissões do Maps antigo");
assert.doesNotMatch(directive("script-src"), /'unsafe-inline'|'unsafe-eval'/, "script inline ou eval não permitido");

assert.match(html, /https:\/\/cdn\.jsdelivr\.net\/npm\/maplibre-gl@5\.24\.0\/dist\/maplibre-gl\.css/);
assert.match(html, /https:\/\/cdn\.jsdelivr\.net\/npm\/maplibre-gl@5\.24\.0\/dist\/maplibre-gl\.js/);
assert.match(readme, /docker compose -f docker-compose\.dev\.yml up --build/);
assert.match(readme, /docker compose --env-file \.env\.production -f docker-compose\.production\.yml up -d --build/);
assert.doesNotMatch(readme, /\n(?:LOAD_DEMO_DATA=false )?docker compose up --build\n/, "não usar compose implícito inexistente");
console.log("CSP, carregamento MapLibre e comandos Docker documentados: OK.");
