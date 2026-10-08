import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";

const elements = new Map();
function get(id) {
    if (!elements.has(id)) elements.set(id, {
        value: "", checked: false, hidden: false, disabled: false, innerHTML: "",
        textContent: "", addEventListener() {},
    });
    return elements.get(id);
}
get("org-seletor").value = "1";
get("relatorio-dias").value = "30";
let papel = "leitor";
const pedidos = [];
const dados = {
    1: { id: 101, nome: "Filial <One>", codigo_filial: "A", unidade_matriz: true, ativo: true },
    2: { id: 202, nome: "Filial Dois", codigo_filial: "B", unidade_matriz: false, ativo: true },
};
const fake = createContext({
    document: { getElementById: get },
    ChurrasPlanEquipe: { papel: () => papel },
    ChurrasPlanAPI: {
        filiaisParceiro: async () => { pedidos.push("filiais"); return [dados[get("org-seletor").value]]; },
        onboardingParceiro: async () => ({ concluidos: 1, total: 4, passos: [
            { concluido: true, titulo: "Cadastro de loja" },
            { concluido: false, titulo: "Verificação administrativa" },
        ] }),
        relatorioComercialParceiro: async () => ({
            totais: { filiais: 1, ofertas_registradas: 2, visualizacoes: 3, cliques_em_rota: 1 },
            unidades: [{ ...dados[get("org-seletor").value],
                ofertas_registradas: 2, visualizacoes: 3, cliques_em_rota: 1 }],
            vendas_confirmadas: null, receita_confirmada: null,
        }),
    },
    escaparHTML: (v) => String(v).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
    console,
});
runInContext(readFileSync("FrontEnd/js/parceiro-operacao.js", "utf8"), fake);
await runInContext("ChurrasPlanOperacao.carregar()", fake);
assert.equal(get("form-filial-meta").hidden, true);
assert.equal(get("operacao-importacoes").hidden, true);
assert.match(get("filiais-lista").innerHTML, /Filial &lt;One&gt;/);
assert.doesNotMatch(get("relatorio-comercial").innerHTML, /receita|faturamento|vendas confirmadas/i);
assert.match(get("onboarding-parceiro").innerHTML, /Verificação administrativa/);
get("org-seletor").value = "2";
papel = "gestor";
await runInContext("ChurrasPlanOperacao.carregar()", fake);
assert.equal(get("form-filial-meta").hidden, false);
assert.equal(get("operacao-importacoes").hidden, false);
assert.match(get("filiais-lista").innerHTML, /Filial Dois/);
assert.doesNotMatch(get("filiais-lista").innerHTML, /Filial &lt;One&gt;/);
get("org-seletor").value = "";
await runInContext("ChurrasPlanOperacao.carregar()", fake);
assert.equal(get("operacao-b2b").hidden, true);
assert.equal(get("operacao-relatorios").hidden, true);
assert.equal(get("operacao-importacoes").hidden, true);
console.log("Operação B2B: isolamento de filiais por tenant, leitura/escrita por papel e métricas não transacionais OK.");
