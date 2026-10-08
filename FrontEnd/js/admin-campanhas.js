/** Moderação administrativa. Aprovação e verificação ocorrem exclusivamente no backend. */
const ChurrasPlanAdminCampanhas = (() => {
    const destino = () => document.getElementById("admin-campanhas-pendentes");
    const esc = (v) => escaparHTML(String(v ?? ""));
    async function carregar() {
        const el = destino();
        const pendentes = await ChurrasPlanAPI.adminCampanhasPendentes();
        el.innerHTML = pendentes.length ? pendentes.map(c => `
          <div class="basket-row"><strong>${esc(c.nome)}</strong>
            <small>Organização #${Number(c.organizacao_id)} · ${esc(c.codigo)} · vigência ${esc(c.inicio_em)} até ${esc(c.fim_em)}</small>
            <p>${c.itens.map(i => `${esc(i.produto)} — ${esc(i.estabelecimento)} R$ ${Number(i.preco).toFixed(2)}`).join("; ")}</p>
            <div>
              <button type="button" data-aprovar-campanha="${Number(c.id)}">Aprovar</button>
              <button type="button" data-rejeitar-campanha="${Number(c.id)}">Rejeitar</button>
            </div>
          </div>`).join("") : '<p class="texto-suave">Nenhuma campanha aguardando moderação.</p>';
    }
    function iniciar() {
        destino().addEventListener("click", async (event) => {
            const aprovar = event.target.closest("[data-aprovar-campanha]");
            const rejeitar = event.target.closest("[data-rejeitar-campanha]");
            if (!aprovar && !rejeitar) return;
            const id = Number(aprovar?.dataset.aprovarCampanha || rejeitar?.dataset.rejeitarCampanha);
            if (!Number.isInteger(id) || id < 1) return;
            let motivo = null;
            if (rejeitar) {
                motivo = window.prompt("Explique o motivo da rejeição (mínimo 8 caracteres):");
                if (motivo === null) return;
                if (motivo.trim().length < 8) {
                    adminMensagem("Informe um motivo de pelo menos oito caracteres.", "erro");
                    return;
                }
            } else if (!window.confirm("Aprovar campanha para exibição pública enquanto vigente?")) return;
            const botao = aprovar || rejeitar;
            botao.disabled = true;
            try {
                await ChurrasPlanAPI.adminRevisarCampanha(id, {
                    aprovar: !!aprovar, motivo: motivo?.trim() || null,
                });
                await carregar();
                await carregarAuditoriaAdmin();
                adminMensagem("Campanha revisada.", "sucesso");
            } catch (erro) {
                adminMensagem(erro.message, "erro");
                botao.disabled = false;
            }
        });
    }
    return { carregar, iniciar };
})();

document.addEventListener("DOMContentLoaded", async () => {
    const user = await ChurrasPlanAuth.usuarioAtual().catch(() => null);
    if (!user || user.papel !== "admin") return;
    ChurrasPlanAdminCampanhas.iniciar();
    try { await ChurrasPlanAdminCampanhas.carregar(); }
    catch (e) { adminMensagem(`Falha ao carregar campanhas pendentes: ${e.message}`, "erro"); }
});
