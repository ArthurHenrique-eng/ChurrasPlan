/** Assinaturas B2B em Stripe TEST. Nenhuma resposta do navegador ativa entitlements. */
const ChurrasPlanBilling = (() => {
    const el = id => document.getElementById(id);
    const esc = v => escaparHTML(String(v ?? ""));
    let estado = null;
    let catalogo = [];

    const formatar = cents => (Number(cents) / 100).toLocaleString("pt-BR", {
        style: "currency", currency: "BRL",
    });

    function chaveNova() {
        return window.crypto?.randomUUID?.() ||
            `checkout-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }

    function renderizarPlanos() {
        const alterar = !!estado?.beneficios_ativos;
        el("billing-planos").innerHTML = catalogo.map(plano => {
            const atual = alterar && estado.plano === plano.plano;
            return `<article class="basket-row"><strong>${esc(plano.plano.toUpperCase())} — ${formatar(plano.centavos)} / mês</strong>
                <small>Preço real configurado no Stripe Test, sem cobrança em produção.</small>
                <button type="button" data-billing-plano="${esc(plano.plano)}" ${atual || estado?.cancelamento_agendado ? "disabled" : ""}>
                  ${atual ? "Plano atual" : alterar ? "Solicitar troca" : "Testar contratação"}
                </button></article>`;
        }).join("") || '<p class="texto-suave">Nenhum plano configurado no Stripe Test.</p>';
    }

    function renderizarResumo() {
        const fim = estado?.periodo_fim_em
            ? new Date(estado.periodo_fim_em + "Z").toLocaleString("pt-BR")
            : "—";
        el("billing-resumo").textContent = `Plano: ${estado?.plano || "free"}. Status Stripe: ${estado?.status || "sem_assinatura"}. Benefícios: ${estado?.beneficios_ativos ? "ativos" : "inativos"}. Válido até: ${fim}.`
            + (estado?.tolerancia_ate ? " Pagamento pendente com tolerância limitada." : "")
            + (estado?.cancelamento_agendado ? " Cancelamento agendado para o fim do período." : "");
        el("billing-sincronizar").hidden = !estado?.checkout_habilitado || !estado?.status || estado.status === "sem_assinatura";
        el("billing-portal").hidden = !estado?.checkout_habilitado || !estado?.beneficios_ativos;
        el("billing-cancelar").hidden = !estado?.checkout_habilitado || !estado?.beneficios_ativos || estado.cancelamento_agendado;
    }

    async function carregar() {
        const proprietario = !!el("org-seletor").value && ChurrasPlanEquipe.papel() === "proprietario";
        el("billing-painel").hidden = !proprietario;
        if (!proprietario) return;
        estado = await ChurrasPlanAPI.billingAssinatura();
        renderizarResumo();
        if (!estado.checkout_habilitado) {
            el("billing-planos").textContent = "Checkout Stripe Test não configurado. Nenhum pagamento poderá ser iniciado.";
            el("billing-faturas").textContent = "Sem histórico de faturas de teste.";
            return;
        }
        const [planos, faturas] = await Promise.all([
            ChurrasPlanAPI.billingCatalogo(), ChurrasPlanAPI.billingFaturas(),
        ]);
        catalogo = planos.planos;
        renderizarPlanos();
        el("billing-faturas").innerHTML = faturas.map(f => `<div class="basket-row">
            <strong>Fatura ${esc(f.id)}</strong>
            <small>${esc(f.status)} · ${esc(f.moeda)} ${Number(f.total_centavos || 0) / 100} · pago ${Number(f.pago_centavos || 0) / 100}</small>
        </div>`).join("") || '<p class="texto-suave">Nenhuma fatura registrada no Stripe Test.</p>';
    }

    function iniciar() {
        el("billing-planos").addEventListener("click", async event => {
            const btn = event.target.closest("[data-billing-plano]");
            if (!btn) return;
            const plano = btn.dataset.billingPlano;
            if (!["pro", "business"].includes(plano) || btn.disabled) return;
            if (!window.confirm(estado?.beneficios_ativos
                ? "Solicitar troca de plano no Stripe Test? A mudança depende de confirmação do pagamento."
                : "Abrir o checkout de teste Stripe? Nenhum cartão real será cobrado.")) return;
            btn.disabled = true;
            try {
                const chave = chaveNova();
                if (estado?.beneficios_ativos) {
                    await ChurrasPlanAPI.billingTrocarPlano({
                        plano, chave_idempotencia: chave,
                    });
                    mensagemParceiro("Mudança solicitada no Stripe Test. O acesso só muda após confirmação do provedor.");
                    await carregar();
                } else {
                    const pedido = await ChurrasPlanAPI.billingCheckout({
                        plano, chave_idempotencia: chave,
                    });
                    window.location.assign(pedido.checkout_url);
                }
            } catch (err) {
                mensagemParceiro(err.message, "erro");
                btn.disabled = false;
            }
        });
        el("billing-sincronizar").addEventListener("click", async event => {
            const b = event.currentTarget; b.disabled = true;
            try {
                await ChurrasPlanAPI.billingSincronizar();
                await carregar();
                mensagemParceiro("Assinatura sincronizada com Stripe Test.");
            } catch (e) { mensagemParceiro(e.message, "erro"); }
            finally { b.disabled = false; }
        });
        el("billing-cancelar").addEventListener("click", async event => {
            if (!window.confirm("Agendar cancelamento da assinatura ao fim do período?")) return;
            const b = event.currentTarget; b.disabled = true;
            try {
                await ChurrasPlanAPI.billingCancelar();
                await carregar();
                mensagemParceiro("Cancelamento agendado junto ao Stripe Test.");
            } catch (e) { mensagemParceiro(e.message, "erro"); }
            finally { b.disabled = false; }
        });
        el("billing-portal").addEventListener("click", async event => {
            const b = event.currentTarget; b.disabled = true;
            try {
                const portal = await ChurrasPlanAPI.billingPortal();
                window.location.assign(portal.portal_url);
            } catch (e) { mensagemParceiro(e.message, "erro"); b.disabled = false; }
        });
    }
    return { carregar, iniciar };
})();
