/** Catálogo e campanhas B2B. O servidor é a autoridade de tenant e permissões. */
const ChurrasPlanComercial = (() => {
    const el = (id) => document.getElementById(id);
    const seguro = (v) => escaparHTML(String(v ?? ""));
    let chave = null, ultimoCSV = null;

    const podeEditar = () => ["proprietario", "gestor", "editor"].includes(ChurrasPlanEquipe.papel());
    const podeGerir = () => ["proprietario", "gestor"].includes(ChurrasPlanEquipe.papel());
    const chaveNova = () => window.crypto?.randomUUID?.() || `lote-${Date.now()}-${Math.random().toString(36).slice(2)}`;

    function renderCampanhas(campanhas) {
        el("campanhas-lista").innerHTML = campanhas.length ? campanhas.map(c => {
            const ofertadas = c.itens.map(i => `${seguro(i.produto)} — ${seguro(i.estabelecimento)} (R$ ${Number(i.preco).toFixed(2)})`).join("; ");
            const editar = podeGerir() && c.status === "rascunho";
            const cancelar = podeGerir() && c.status !== "cancelada";
            const renovar = podeGerir() && c.status === "rejeitada";
            return `<div class="basket-row"><strong>${seguro(c.nome)}</strong>
              <small>${seguro(c.codigo)} · ${seguro(c.status)} · início: ${seguro(c.inicio_em)} · fim: ${seguro(c.fim_em)}</small>
              <p class="texto-suave">${ofertadas}</p>
              ${c.motivo_revisao ? `<small>Motivo: ${seguro(c.motivo_revisao)}</small>` : ""}
              <div>${editar ? `<button type="button" data-campanha-enviar="${Number(c.id)}">Enviar para revisão</button>` : ""}
                ${renovar ? `<small>Campanha rejeitada: edite os dados pela API antes do reenvio.</small>` : ""}
                ${cancelar ? `<button type="button" data-campanha-cancelar="${Number(c.id)}">Cancelar campanha</button>` : ""}</div></div>`;
        }).join("") : '<p class="texto-suave">Nenhuma campanha cadastrada nesta organização.</p>';
    }

    async function carregar() {
        const org = el("org-seletor").value;
        el("catalogo-massa").hidden = !org || !podeEditar();
        el("campanhas-painel").hidden = !org;
        if (!org) return;
        el("form-campanha").hidden = !podeGerir();
        const [campanhas, ofertas] = await Promise.all([
            ChurrasPlanAPI.campanhasParceiro(),
            ChurrasPlanAPI.ofertasCampanhaParceiro(),
        ]);
        renderCampanhas(campanhas);
        const campo = el("campanha-ofertas");
        campo.innerHTML = ofertas.map(o => `<option value="${Number(o.id)}">#${Number(o.id)} · ${seguro(o.produto)} — ${seguro(o.estabelecimento)} (R$ ${Number(o.preco).toFixed(2)})${o.verificada ? "" : " · aguardando verificação"}</option>`).join("");
        el("form-campanha").querySelector('button[type="submit"]').disabled = !ofertas.length;
    }

    function iniciar() {
        el("catalogo-arquivo").addEventListener("change", async (e) => {
            const arq = e.target.files?.[0];
            if (!arq) return;
            if (arq.size > 100000) {
                mensagemParceiro("O arquivo ultrapassa 100 KB.", "erro");
                e.target.value = "";
                return;
            }
            el("catalogo-texto").value = await arq.text();
            chave = null;
        });
        el("catalogo-texto").addEventListener("input", () => { chave = null; });
        el("form-catalogo-massa").addEventListener("submit", async (e) => {
            e.preventDefault();
            const botao = e.target.querySelector('button[type="submit"]');
            botao.disabled = true;
            const texto = el("catalogo-texto").value.trim();
            if (!chave || ultimoCSV !== texto) {
                chave = chaveNova();
                ultimoCSV = texto;
            }
            try {
                const r = await ChurrasPlanAPI.importarCatalogoCSV({
                    chave_idempotencia: chave, csv_texto: texto,
                });
                el("catalogo-resultado").textContent =
                    `${r.criados} SKUs criados; ${r.atualizados} atualizados; ${r.rejeitados} rejeitados.`
                    + (r.repetida ? " Reenvio idempotente, sem alterações adicionais." : "")
                    + (r.erros?.length ? " " + r.erros.map(x => `linha ${x.linha}: ${x.erro}`).join("; ") : "");
                chave = null;
                await carregar();
                await carregarParceiro();
                mensagemParceiro("Importação de catálogo processada.");
            } catch (err) { mensagemParceiro(err.message, "erro"); }
            finally { botao.disabled = false; }
        });
        el("form-campanha").addEventListener("submit", async (e) => {
            e.preventDefault();
            const botao = e.target.querySelector('button[type="submit"]');
            botao.disabled = true;
            try {
                const preco_ids = [...el("campanha-ofertas").selectedOptions].map(o => Number(o.value));
                if (!preco_ids.length) throw new Error("Selecione pelo menos uma oferta cadastrada.");
                const payload = {
                    codigo: el("campanha-codigo").value.trim(),
                    nome: el("campanha-nome").value.trim(),
                    descricao: el("campanha-descricao").value.trim() || null,
                    inicio_em: new Date(el("campanha-inicio").value).toISOString(),
                    fim_em: new Date(el("campanha-fim").value).toISOString(),
                    preco_ids,
                };
                const c = await ChurrasPlanAPI.criarCampanhaParceiro(payload);
                e.target.reset();
                await carregar();
                mensagemParceiro(`Campanha #${c.id} criada em rascunho. Envie para revisão para solicitar a aprovação.`);
            } catch (err) { mensagemParceiro(err.message, "erro"); }
            finally { botao.disabled = false; }
        });
        el("campanhas-lista").addEventListener("click", async (e) => {
            const enviar = e.target.closest("[data-campanha-enviar]");
            const cancelar = e.target.closest("[data-campanha-cancelar]");
            if (!enviar && !cancelar) return;
            const id = Number(enviar?.dataset.campanhaEnviar || cancelar?.dataset.campanhaCancelar);
            if (!Number.isInteger(id) || id <= 0) return;
            if (cancelar && !window.confirm("Cancelar esta campanha?")) return;
            try {
                if (enviar) await ChurrasPlanAPI.enviarCampanhaParceiro(id);
                else await ChurrasPlanAPI.cancelarCampanhaParceiro(id);
                await carregar();
                mensagemParceiro("Status da campanha atualizado.");
            } catch (err) { mensagemParceiro(err.message, "erro"); }
        });
    }
    return { iniciar, carregar };
})();
