/** Fase 2C: cabeçalho por tenant e seletor não vazam dados entre organizações. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const chamadas = [];
const estado = new Map();
const fakeStorage = {
    getItem: (key) => estado.get(key) || null,
    setItem: (key, value) => estado.set(key, String(value)),
    removeItem: (key) => estado.delete(key),
};
const nodes = new Map();
const get = (id) => {
    if (!nodes.has(id)) nodes.set(id, {
        value: "", hidden: false, disabled: false, innerHTML: "", textContent: "",
        listeners: new Map(), options: [{ value: "leitor", disabled: false }, { value: "gestor", disabled: false }],
        addEventListener(event, callback) { this.listeners.set(event, callback); },
        querySelector() { return { value: "leitor" }; },
    });
    return nodes.get(id);
};
const orgs = [
    { id: 10, nome: "Mercado A", papel: "proprietario" },
    { id: 20, nome: "Mercado B", papel: "leitor" },
];
const sandbox = createContext({
    sessionStorage: fakeStorage,
    document: {
        cookie: "", getElementById: get, addEventListener: () => {},
    },
    window: {
        setTimeout() { return 1; }, clearTimeout() {}, confirm: () => true,
    },
    AbortController,
    URLSearchParams,
    API_BASE_URL: "https://api.example.test",
    fetch: async (url, options) => {
        chamadas.push({ url, options });
        const path = url.replace("https://api.example.test", "");
        let data = [];
        if (path === "/api/parceiro/organizacoes") data = orgs;
        if (path === "/api/parceiro/entitlements") data = {
            plano: "free", equipe: { ativos: 2, convites_pendentes: 0, limite: 3 },
        };
        return { ok: true, json: async () => data };
    },
    escaparHTML: (x) => String(x).replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
    mensagemParceiro() {},
    console,
});

runInContext(readFileSync("FrontEnd/js/api.js", "utf8"), sandbox);
runInContext(readFileSync("FrontEnd/js/parceiro-equipe.js", "utf8"), sandbox);

let chamadasRecarregar = 0;
const executar = (js) => runInContext(js, sandbox);
await executar('ChurrasPlanEquipe.iniciar({id: 7, papel: "parceiro"}, async () => {})');
assert.equal(estado.get("churrasplan_organizacao_id"), "10");
assert.equal(get("equipe-painel").hidden, false);
assert.equal(get("form-produto").hidden, false);

await get("org-seletor").listeners.get("change").call(null, Object.assign({}, {}));
assert.equal(estado.get("churrasplan_organizacao_id"), "10");
get("org-seletor").value = "20";
await get("org-seletor").listeners.get("change")();
assert.equal(estado.get("churrasplan_organizacao_id"), "20");
assert.equal(get("equipe-painel").hidden, true);
assert.equal(get("form-estabelecimento").hidden, true);
assert.equal(get("form-produto").hidden, true);
assert.equal(get("form-preco").hidden, true);

await executar("ChurrasPlanAPI.dashboardParceiro()");
assert.equal(chamadas.at(-1).options.headers["X-Organizacao-ID"], "20");
await executar("ChurrasPlanAPI.organizacoesParceiro()");
assert.equal(chamadas.at(-1).options.headers["X-Organizacao-ID"], undefined);
assert.equal(estado.get("churrasplan_organizacao_id"), "20");
console.log("Seleção multi-tenant, cabeçalho B2B e bloqueio de formulários para leitor: OK");
