import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const script = readFileSync("FrontEnd/js/parceiro.js", "utf8");
const elements = new Map();
const get = (id) => {
    if (!elements.has(id)) elements.set(id, { innerHTML: "", textContent: "", value: "", disabled: false });
    return elements.get(id);
};
const gen = [
    { id: 11, nome: "Água", categoria_nome: "Bebidas", preco_referencia: 3.99, preco_referencia_unidade: "garrafa" },
    { id: 12, nome: "Detergente", categoria_nome: "Limpeza", preco_referencia: null, preco_referencia_unidade: null },
];
const results = {
    dashboardParceiro: () => Promise.reject(new Error("Falha nas métricas")),
    estabelecimentosParceiro: () => Promise.resolve([]),
    produtosParceiro: () => Promise.resolve([]),
    listarGenericos: () => Promise.resolve(gen),
};
let lastMessage = "";
const sandbox = createContext({
    document: { getElementById: get, addEventListener: () => {} },
    ChurrasPlanAPI: results,
    escaparHTML: (v) => String(v).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
    mostrarMensagem: (_, msg) => { lastMessage = msg; },
    console,
});

runInContext(script, sandbox, { filename: "parceiro.js" });
await runInContext("carregarParceiro()", sandbox);
assert.match(lastMessage, /métricas/, "falha parcial deve ser informada");
assert.match(get("prod-categoria").innerHTML, /Bebidas/);
assert.match(get("prod-categoria").innerHTML, /Limpeza/);
get("prod-categoria").value = "Bebidas";
runInContext("renderProdutosGenericos()", sandbox);
assert.equal(get("prod-pai").disabled, false);
assert.match(get("prod-pai").innerHTML, /Água/);
assert.match(get("prod-pai").innerHTML, /ref. estimada R\$ 3,99\/garrafa/);
get("prod-categoria").value = "Limpeza";
runInContext("renderProdutosGenericos()", sandbox);
assert.match(get("prod-pai").innerHTML, /Detergente/);
assert.doesNotMatch(get("prod-pai").innerHTML, /R\$/, "não inventar preço de limpeza");

results.dashboardParceiro = () => Promise.resolve({
    estabelecimentos: 0, estabelecimentos_verificados: 0, ofertas_cadastradas: 0,
    visualizacoes: 0, cliques: 0, mensagem_verificacao: "ok",
});
results.listarGenericos = () => Promise.reject(new Error("API indisponível"));
get("prod-categoria").value = "";
await runInContext("carregarParceiro()", sandbox);
assert.match(get("prod-catalogo-ajuda").textContent, /Falha ao consultar/);
assert.equal(get("prod-pai").disabled, true);
assert.match(lastMessage, /catálogo genérico/);
console.log("Catálogo parceiro: carregamento parcial, categoria, preço e falha tratados.");
