/** Fase 3: recursos financeiros só aparecem ao proprietário do tenant. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const nodes = new Map();
const el = id => {
    if (!nodes.has(id)) nodes.set(id, {
        value: "", hidden: false, innerHTML: "", textContent: "",
        listeners: {}, addEventListener(name, cb) { this.listeners[name] = cb; },
    });
    return nodes.get(id);
};
let role = "leitor";
let enabled = false;
let calls = 0;
el("org-seletor").value = "10";
const sandbox = createContext({
    document: { getElementById: el },
    ChurrasPlanEquipe: { papel: () => role },
    ChurrasPlanAPI: {
        billingAssinatura: async () => {
            calls++;
            return {
                plano: "free", status: "sem_assinatura", beneficios_ativos: false,
                checkout_habilitado: enabled, cancelamento_agendado: false,
                periodo_fim_em: null,
            };
        },
        billingCatalogo: async () => ({ planos: [
            {plano: "pro", centavos: 2990},
            {plano: "business", centavos: 8990},
        ] }),
        billingFaturas: async () => [],
    },
    escaparHTML: v => String(v).replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
    console,
});
runInContext(readFileSync("FrontEnd/js/parceiro-billing.js", "utf8"), sandbox);
await runInContext("ChurrasPlanBilling.carregar()", sandbox);
assert.equal(calls, 0);
assert.equal(el("billing-painel").hidden, true);
role = "proprietario";
await runInContext("ChurrasPlanBilling.carregar()", sandbox);
assert.equal(calls, 1);
assert.equal(el("billing-painel").hidden, false);
assert.match(el("billing-planos").textContent, /não configurado/);
enabled = true;
await runInContext("ChurrasPlanBilling.carregar()", sandbox);
assert.equal(calls, 2);
assert.match(el("billing-planos").innerHTML, /Pro/i);
assert.match(el("billing-planos").innerHTML, /29,90/);
role = "gestor";
await runInContext("ChurrasPlanBilling.carregar()", sandbox);
assert.equal(calls, 2);
assert.equal(el("billing-painel").hidden, true);
el("org-seletor").value = "";
role = "proprietario";
await runInContext("ChurrasPlanBilling.carregar()", sandbox);
assert.equal(calls, 2);
assert.equal(el("billing-painel").hidden, true);
console.log("Fase 3: painel proprietário/tenant, preços Stripe Test e bloqueio sem configuração OK");
