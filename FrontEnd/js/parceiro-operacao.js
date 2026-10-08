/** Operação das lojas B2B; todas as permissões finais são verificadas na API. */
const ChurrasPlanOperacao = (() => {
    const el = (id) => document.getElementById(id);
    const safe = (v) => escaparHTML(String(v ?? ""));
    let lojas = [];
    let chavePendente = null, ultimoTexto = null;

    function gerencia() {
        return ["proprietario", "gestor"].includes(ChurrasPlanEquipe.papel());
    }
    function podePublicar() {
        return ["proprietario", "gestor", "editor"].includes(ChurrasPlanEquipe.papel());
    }
    function preencherEdicao(id) {
        const loja = lojas.find(x => Number(x.id) === Number(id));
        if (!loja) return;
        el("filial-codigo").value = loja.codigo_filial || "";
        el("filial-matriz").checked = !!loja.unidade_matriz;
        el("filial-ativa").checked = !!loja.ativo;
    }
    function renderFiliais(items) {
        lojas = items;
        const lista = el("filiais-lista");
        lista.innerHTML = items.length
            ? items.map(e => `<div class="basket-row"><strong>${safe(e.nome)}</strong>
                <small>${safe(e.codigo_filial || "Sem código")} · ${e.unidade_matriz ? "Matriz" : "Filial"} · ${e.ativo ? "Ativa" : "Inativa"} · ${e.parceiro_verificado ? "Verificada" : "Aguardando verificação"}</small>
                </div>`).join("")
            : '<p class="texto-suave">Cadastre um estabelecimento para organizar filiais.</p>';
        el("form-filial-meta").hidden = !gerencia() || !items.length;
        const select = el("filial-editar-id");
        const atual = select.value;
        select.innerHTML = items.map(e => `<option value="${Number(e.id)}">${safe(e.nome)}</option>`).join("");
        select.value = items.some(e => String(e.id) === String(atual)) ? atual : (items[0] ? String(items[0].id) : "");
        preencherEdicao(select.value);
    }
    function renderOnboarding(info) {
        el("onboarding-parceiro").innerHTML = `<p class="texto-suave">${Number(info.concluidos)} de ${Number(info.total)} etapas concluídas.</p>
        <ul>${info.passos.map(p => `<li>${p.concluido ? "Concluído" : "Pendente"} — ${safe(p.titulo)}</li>`).join("")}</ul>`;
    }
    function renderRelatorio(report) {
        const totais = report.totais;
        el("relatorio-comercial").innerHTML = `
          <p class="texto-suave">${Number(totais.filiais)} unidades; ${Number(totais.ofertas_registradas)} ofertas registradas; ${Number(totais.visualizacoes)} visualizações e ${Number(totais.cliques_em_rota)} cliques de rota.</p>
          <div class="basket-table">${report.unidades.map(u => `
            <div class="basket-row"><strong>${safe(u.nome)}</strong>
            <small>${Number(u.ofertas_registradas)} ofertas · ${Number(u.visualizacoes)} visualizações · ${Number(u.cliques_em_rota)} cliques em rota</small></div>
          `).join("") || '<p class="texto-suave">Sem unidades cadastradas.</p>'}</div>`;
    }
    async function carregar() {
        if (!el("org-seletor").value) {
            el("operacao-b2b").hidden = true;
            el("operacao-importacoes").hidden = true;
            el("operacao-relatorios").hidden = true;
            return;
        }
        el("operacao-b2b").hidden = false;
        el("operacao-importacoes").hidden = !podePublicar();
        el("operacao-relatorios").hidden = false;
        // Todos os endpoints ficam ligados à organização selecionada.
        const [filiais, onboarding, relatorio] = await Promise.all([
            ChurrasPlanAPI.filiaisParceiro(),
            ChurrasPlanAPI.onboardingParceiro(),
            ChurrasPlanAPI.relatorioComercialParceiro(el("relatorio-dias").value),
        ]);
        renderFiliais(filiais);
        renderOnboarding(onboarding);
        renderRelatorio(relatorio);
    }
    function iniciar() {
        el("filial-editar-id").addEventListener("change", (e) => preencherEdicao(e.target.value));
        el("form-filial-meta").addEventListener("submit", async (e) => {
            e.preventDefault();
            const botao = e.target.querySelector('button[type="submit"]');
            botao.disabled = true;
            try {
                await ChurrasPlanAPI.alterarFilial(Number(el("filial-editar-id").value), {
                    codigo_filial: el("filial-codigo").value.trim().toUpperCase() || null,
                    unidade_matriz: el("filial-matriz").checked,
                    ativo: el("filial-ativa").checked,
                });
                await carregar();
                mensagemParceiro("Dados da filial atualizados.");
            } catch (err) { mensagemParceiro(err.message, "erro"); }
            finally { botao.disabled = false; }
        });
        el("importar-csv-arquivo").addEventListener("change", async (e) => {
            const arquivo = e.target.files?.[0];
            if (!arquivo) return;
            if (arquivo.size > 100000) {
                mensagemParceiro("O arquivo excede 100 KB.", "erro");
                e.target.value = "";
                return;
            }
            el("importar-csv-texto").value = await arquivo.text();
            chavePendente = null;
        });
        el("importar-csv-texto").addEventListener("input", () => { chavePendente = null; });
        el("form-importar-ofertas").addEventListener("submit", async (e) => {
            e.preventDefault();
            const botao = e.target.querySelector('button[type="submit"]');
            botao.disabled = true;
            const texto = el("importar-csv-texto").value.trim();
            if (!chavePendente || ultimoTexto !== texto) {
                chavePendente = (window.crypto?.randomUUID?.() ||
                    `lote-${Date.now()}-${Math.random().toString(36).slice(2)}`);
                ultimoTexto = texto;
            }
            try {
                const retorno = await ChurrasPlanAPI.importarOfertasCSV({
                    chave_idempotencia: chavePendente, csv_texto: texto,
                });
                el("importar-csv-resultado").textContent = `${retorno.criadas} ofertas criadas; ${retorno.rejeitadas} linhas rejeitadas.`
                    + (retorno.repetida ? " Lote já importado: nenhuma oferta duplicada." : "")
                    + (retorno.erros?.length ? " Erros: " + retorno.erros.map(er => `linha ${er.linha}: ${er.erro}`).join("; ") : "");
                chavePendente = null;
                await carregar();
                mensagemParceiro("Importação processada.");
            } catch (err) { mensagemParceiro(err.message, "erro"); }
            finally { botao.disabled = false; }
        });
        el("relatorio-dias").addEventListener("change", async () => {
            try { await carregar(); } catch (e) { mensagemParceiro(e.message, "erro"); }
        });
    }
    return { iniciar, carregar };
})();
