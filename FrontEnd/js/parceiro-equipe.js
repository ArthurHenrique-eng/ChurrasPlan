/** Interface B2B da equipe. Seleção por aba; autorização sempre no backend. */
const ChurrasPlanEquipe = (() => {
    let orgs = [], orgAtiva = null, usuario = null, emTransicao = false;
    const el = (id) => document.getElementById(id);
    const seguro = (s) => escaparHTML(String(s ?? ""));
    const PAPEIS = ["proprietario", "gestor", "editor", "leitor"];

    function guardarOrganizacao(id) {
        ChurrasPlanAPI.definirOrganizacaoAtiva(id);
        try {
            if (id) sessionStorage.setItem("churrasplan_organizacao_id", String(id));
            else sessionStorage.removeItem("churrasplan_organizacao_id");
        } catch { /* armazenamento opcional; cabeçalho não será enviado */ }
    }

    function perfil() { return orgAtiva?.papel || null; }
    function podeGerir() { return perfil() === "proprietario" || perfil() === "gestor"; }
    function permissaoEdicao() { return perfil() !== "leitor"; }

    function aplicarPermissoes() {
        const forms = ["form-estabelecimento", "form-produto", "form-preco"];
        // A UI orienta, mas é o backend que impõe efetivamente o RBAC.
        for (const id of forms) el(id).hidden = !permissaoEdicao();
        const localizar = el("est-localizar-endereco");
        localizar.disabled = !permissaoEdicao();
        el("equipe-painel").hidden = !orgAtiva || !podeGerir();
        el("org-perfil").textContent = orgAtiva
            ? `Seu papel: ${perfil()}.` : "Visão administrativa global; selecione uma organização para gerir a equipe.";
        for (const opt of el("equipe-papel").options) {
            opt.disabled = perfil() === "gestor" && !["editor", "leitor"].includes(opt.value);
        }
        if (perfil() === "gestor" && !["editor", "leitor"].includes(el("equipe-papel").value)) {
            el("equipe-papel").value = "leitor";
        }
    }

    function renderMembros(membros) {
        el("equipe-membros").innerHTML = membros.length
            ? membros.map((m) => {
                const me = Number(m.usuario_id) === Number(usuario.id);
                const operavel = !me && (perfil() === "proprietario" || ["editor", "leitor"].includes(m.papel));
                const opcoes = PAPEIS.filter(p => perfil() === "proprietario" || ["editor", "leitor"].includes(p))
                    .map(p => `<option value="${p}" ${m.papel === p ? "selected" : ""}>${seguro(p)}</option>`).join("");
                const botoes = operavel
                    ? `<label>Alterar papel <select data-membro-papel="${Number(m.usuario_id)}">${opcoes}</select></label>
                       <button type="button" data-alterar-membro="${Number(m.usuario_id)}">Salvar papel</button>
                       <button type="button" data-remover-membro="${Number(m.usuario_id)}">Remover acesso</button>`
                    : `<small>Sem permissão para alterar esta conta</small>`;
                return `<div class="basket-row"><strong>${seguro(m.nome)}</strong>
                    <small>${seguro(m.email)} · ${seguro(m.papel)}${me ? " · você" : ""}</small>
                    <div>${botoes}</div></div>`;
            }).join("") : '<p class="texto-suave">Nenhum membro encontrado.</p>';
    }

    function renderConvites(convites) {
        el("equipe-convites").innerHTML = convites.length
            ? convites.map((c) => {
                const gerenciavel = perfil() === "proprietario" || ["editor", "leitor"].includes(c.papel);
                return `<div class="basket-row"><strong>${seguro(c.email)}</strong>
                    <small>${seguro(c.papel)} · expira em ${seguro(new Date(c.expira_em).toLocaleDateString("pt-BR"))}</small>
                    ${gerenciavel ? `<button type="button" data-revogar-convite="${Number(c.id)}">Revogar convite</button>` : ""}</div>`;
            }).join("") : '<p class="texto-suave">Não há convites pendentes.</p>';
    }

    async function carregarEquipe() {
        if (!orgAtiva) { el("org-limites").textContent = ""; return; }
        // Exibir consumo sem conceder direitos por JavaScript.
        const limites = await ChurrasPlanAPI.entitlementsParceiro();
        const equipe = limites.equipe;
        el("org-limites").textContent = equipe
            ? `Plano ${limites.plano.toUpperCase()}; equipe: ${equipe.ativos} membro(s) + ${equipe.convites_pendentes} convite(s) / ${equipe.limite} vaga(s).`
            : "";
        if (!podeGerir()) return;
        const [membros, convites] = await Promise.all([
            ChurrasPlanAPI.membrosOrganizacao(), ChurrasPlanAPI.convitesOrganizacao(),
        ]);
        renderMembros(membros);
        renderConvites(convites);
    }

    async function selecionar(id, recarregar) {
        if (emTransicao) return;
        emTransicao = true;
        el("org-seletor").disabled = true;
        try {
            orgAtiva = orgs.find(o => String(o.id) === String(id)) || null;
            guardarOrganizacao(orgAtiva?.id);
            aplicarPermissoes();
            await recarregar();
            await carregarEquipe();
        } finally {
            emTransicao = false;
            el("org-seletor").disabled = false;
        }
    }

    async function iniciar(user, recarregar) {
        usuario = user;
        orgs = await ChurrasPlanAPI.organizacoesParceiro();
        const sel = el("org-seletor");
        sel.innerHTML = (user.papel === "admin" ? '<option value="">Visão administrativa global</option>' : "")
            + orgs.map(o => `<option value="${Number(o.id)}">${seguro(o.nome)} (${seguro(o.papel)})</option>`).join("");
        let salvo = null;
        try { salvo = sessionStorage.getItem("churrasplan_organizacao_id"); } catch { /* ignorar */ }
        const escolhido = orgs.find(o => String(o.id) === salvo)
            || (user.papel === "admin" ? null : orgs[0] || null);
        // Não escolher um ID antigo pertencente a outra conta.
        sel.value = escolhido ? String(escolhido.id) : "";
        if (!escolhido && user.papel !== "admin") {
            throw new Error("Sua conta não possui organização ativa. Solicite um convite válido.");
        }
        await selecionar(sel.value, recarregar);
        sel.addEventListener("change", async () => {
            try { await selecionar(sel.value, recarregar); }
            catch (e) { mensagemParceiro(e.message, "erro"); }
        });
        el("form-convite-equipe").addEventListener("submit", async (e) => {
            e.preventDefault();
            const botao = e.target.querySelector('button[type="submit"]');
            botao.disabled = true;
            try {
                const envio = await ChurrasPlanAPI.enviarConviteOrganizacao({
                    email: el("equipe-email").value.trim(), papel: el("equipe-papel").value,
                });
                e.target.reset();
                el("equipe-token-dev").textContent = envio.dev_token
                    ? `Ambiente de desenvolvimento: link de teste — parceiro.html?convite=${envio.dev_token}`
                    : "Convite enviado por e-mail.";
                await carregarEquipe();
                mensagemParceiro("Convite criado.");
            } catch (err) { mensagemParceiro(err.message, "erro"); }
            finally { botao.disabled = false; }
        });
        el("equipe-membros").addEventListener("click", async (e) => {
            const edit = e.target.closest("[data-alterar-membro]");
            const remove = e.target.closest("[data-remover-membro]");
            if (!edit && !remove) return;
            const id = Number(edit?.dataset.alterarMembro || remove?.dataset.removerMembro);
            if (!Number.isInteger(id) || id < 1) return;
            if (remove && !window.confirm("Remover o acesso desta pessoa à organização?")) return;
            try {
                if (edit) {
                    const campo = el("equipe-membros").querySelector(`[data-membro-papel="${id}"]`);
                    await ChurrasPlanAPI.alterarPapelMembro(id, campo.value);
                } else await ChurrasPlanAPI.removerMembroOrganizacao(id);
                await carregarEquipe();
                mensagemParceiro("Equipe atualizada.");
            } catch (err) { mensagemParceiro(err.message, "erro"); }
        });
        el("equipe-convites").addEventListener("click", async (e) => {
            const botao = e.target.closest("[data-revogar-convite]");
            if (!botao) return;
            if (!window.confirm("Revogar este convite pendente?")) return;
            try {
                await ChurrasPlanAPI.revogarConviteOrganizacao(Number(botao.dataset.revogarConvite));
                await carregarEquipe();
                mensagemParceiro("Convite revogado.");
            } catch (err) { mensagemParceiro(err.message, "erro"); }
        });
    }

    return { iniciar, papel: perfil };
})();
