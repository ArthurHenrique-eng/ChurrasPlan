/** Fase 4A: UI B2B responde ao tenant e aos papéis sem HTML inseguro. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const fields = new Map();
function element(id) {
    if (!fields.has(id)) fields.set(id, {
        value: "", hidden: false, disabled: false, innerHTML: "", textContent: "",
        selectedOptions: [], addEventListener() {},
        querySelector: () => ({disabled: false}),
    });
    return fields.get(id);
}
element("org-seletor").value = "10";
let papel = "leitor";
const chamados = [];
const estado = createContext({
    document: {getElementById: element},
    escaparHTML: x => String(x).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
    ChurrasPlanEquipe: {papel: () => papel},
    ChurrasPlanAPI: {
        campanhasParceiro: async () => { chamados.push("campanhas"); return [{
            id: 5, organizacao_id: 10, nome: "<script>", codigo: "C1",
            status: "rascunho", inicio_em: "2026-11-01", fim_em: "2026-11-30",
            itens: [{produto:"Água", estabelecimento:"Loja", preco:4.5}],
        }]; },
        ofertasCampanhaParceiro: async () => { chamados.push("ofertas"); return [{
            id: 11, produto: "<img>", estabelecimento:"Loja", preco:4.5, verificada: false,
        }]; },
    },
    window: {confirm: () => true, crypto: {randomUUID: () => "lote-2026-test-uuid"}},
    console,
});
runInContext(readFileSync("FrontEnd/js/parceiro-comercial.js", "utf8"), estado);
await runInContext("ChurrasPlanComercial.carregar()", estado);
assert.equal(element("catalogo-massa").hidden, true);
assert.equal(element("form-campanha").hidden, true);
assert.equal(element("campanhas-painel").hidden, false);
assert.match(element("campanhas-lista").innerHTML, /&lt;script&gt;/);
assert.doesNotMatch(element("campanhas-lista").innerHTML, /<script>/);
assert.match(element("campanha-ofertas").innerHTML, /&lt;img&gt;/);
papel = "editor";
await runInContext("ChurrasPlanComercial.carregar()", estado);
assert.equal(element("catalogo-massa").hidden, false);
assert.equal(element("form-campanha").hidden, true);
papel = "gestor";
await runInContext("ChurrasPlanComercial.carregar()", estado);
assert.equal(element("form-campanha").hidden, false);
element("org-seletor").value = "";
const antes = chamados.length;
await runInContext("ChurrasPlanComercial.carregar()", estado);
assert.equal(chamados.length, antes);
assert.equal(element("catalogo-massa").hidden, true);
assert.equal(element("campanhas-painel").hidden, true);
console.log("Painel Fase 4A: RBAC de SKU/campanha, escopo organizacional e HTML escapado OK.");
