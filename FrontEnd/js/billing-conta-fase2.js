/** Stripe Sandbox: permissions come from authenticated API, not browser redirects. */
document.addEventListener("DOMContentLoaded", async () => {
    const pessoal = document.getElementById("conta-billing-pessoal");
    const mercado = document.getElementById("conta-billing-mercado");
    if (!pessoal || !mercado) return;
    const element = (tag, value, cls) => {
        const el = document.createElement(tag);
        if (value !== undefined) el.textContent = String(value);
        if (cls) el.className = cls;
        return el;
    };
    const say = (el, msg) => el.replaceChildren(element("p", msg));
    const button = (label, callback) => {
        const b = element("button", label, "botao botao--secundario");
        b.type = "button";
        b.onclick = async () => {
            b.disabled = true;
            try { await callback(); }
            catch (err) { window.alert(err.message || "Erro ao atualizar assinatura."); }
            finally { b.disabled = false; }
        };
        return b;
    };
    const brl = n => (Number(n) / 100).toLocaleString("pt-BR", {style:"currency", currency:"BRL"});
    const resumo = r => "Plano: " + (r.plano || "free") + " · Status: " +
        (r.status || "sem_assinatura") + " · Benefícios " + (r.beneficios_ativos ? "ativos" : "inativos") +
        (r.cancelamento_agendado ? " · Cancelamento agendado" : "") +
        (r.tolerancia_ate ? " · Inadimplência: tolerância limitada" : "");
    function renderFaturas(el, faturas) {
        el.appendChild(element("h3", "Faturas de teste"));
        if (!faturas.length) { el.appendChild(element("p", "Nenhuma fatura encontrada.")); return; }
        const ul = element("ul");
        for (const f of faturas) {
            ul.appendChild(element("li", f.id + " · " + f.status + " · " +
                brl(f.total_centavos || 0) + " · pago " + brl(f.pago_centavos || 0)));
        }
        el.appendChild(ul);
    }
    async function carregarPessoal() {
        let assinatura;
        try { assinatura = await ChurrasPlanAPI.billingUsuarioAssinatura(); }
        catch (e) { say(pessoal, "Falha na assinatura pessoal: " + e.message); return; }
        pessoal.replaceChildren(element("h3", "Premium pessoal"), element("p", resumo(assinatura)));
        if (assinatura.checkout_habilitado) {
            const controls = element("div", undefined, "history-actions");
            if (assinatura.status !== "sem_assinatura") {
                controls.appendChild(button("Gerenciar no Stripe Test", async () => {
                    const res = await ChurrasPlanAPI.billingUsuarioPortal();
                    window.location.assign(res.portal_url);
                }));
                if (assinatura.cancelamento_agendado && assinatura.beneficios_ativos) {
                    controls.appendChild(button("Reativar renovação", async () => {
                        if (!confirm("Desfazer cancelamento programado no Stripe Test?")) return;
                        await ChurrasPlanAPI.billingUsuarioReativar();
                        await carregarPessoal();
                    }));
                } else if (assinatura.beneficios_ativos) {
                    controls.appendChild(button("Cancelar ao fim do período", async () => {
                        if (!confirm("Agendar cancelamento ao fim do período no Stripe Test?")) return;
                        await ChurrasPlanAPI.billingUsuarioCancelar();
                        await carregarPessoal();
                    }));
                    const novoPeriodo = assinatura.periodicidade === "anual" ? "mensal" : "anual";
                    controls.appendChild(button("Trocar para " + novoPeriodo, async () => {
                        if (!confirm("Alterar o período no Stripe Test? Pode gerar fatura de teste.")) return;
                        await ChurrasPlanAPI.billingUsuarioTrocarPeriodo({
                            periodicidade: novoPeriodo,
                            chave_idempotencia: window.crypto?.randomUUID?.() || "troca-" + Date.now(),
                        });
                        await carregarPessoal();
                    }));
                } else {
                    controls.appendChild(button("Sincronizar pagamento", async () => {
                        await ChurrasPlanAPI.billingUsuarioSincronizar();
                        await carregarPessoal();
                    }));
                }
            } else {
                const link = element("a", "Conhecer Premium", "botao botao--secundario");
                link.href = "planos.html";
                controls.appendChild(link);
            }
            pessoal.appendChild(controls);
        }
        try { renderFaturas(pessoal, await ChurrasPlanAPI.billingUsuarioFaturas()); }
        catch (e) { pessoal.appendChild(element("p", "Faturas indisponíveis: " + e.message)); }
    }
    async function carregarMercado(orgId, etapa) {
        // Explicit tenant header; API still enforces ownership and CSRF.
        const opts = {headers: {"X-Organizacao-ID": String(orgId)}};
        mercado.replaceChildren(element("h3", "Assinatura do mercado"));
        const msg = element("p", "Conferindo a assinatura Stripe Test da organização...");
        mercado.appendChild(msg);
        try {
            let assinatura = await ChurrasPlanAPI.billingAssinatura(opts);
            if (etapa === "retorno" || etapa === "portal") {
                for (let i = 0; i < 5; i++) {
                    assinatura = await ChurrasPlanAPI.billingSincronizar(opts);
                    if (assinatura.beneficios_ativos || assinatura.status !== "sem_assinatura") break;
                    if (i < 4) await new Promise(resolve => setTimeout(resolve, 2000));
                }
            }
            msg.textContent = "Organização #" + orgId + ": " + resumo(assinatura);
            if (etapa === "retorno" && !assinatura.beneficios_ativos) {
                mercado.appendChild(element("p", "Checkout retornou sem confirmação. Confira o webhook e sincronize novamente."));
            }
            const controls = element("div", undefined, "history-actions");
            controls.appendChild(button("Sincronizar assinatura", async () => {
                await ChurrasPlanAPI.billingSincronizar(opts);
                await carregarMercado(orgId, null);
            }));
            controls.appendChild(button("Portal do mercado", async () => {
                const r = await ChurrasPlanAPI.billingPortal(opts);
                location.assign(r.portal_url);
            }));
            if (assinatura.cancelamento_agendado && assinatura.beneficios_ativos) {
                controls.appendChild(button("Reativar renovação", async () => {
                    if (!confirm("Reativar a assinatura de mercado no Stripe Test?")) return;
                    await ChurrasPlanAPI.billingReativar(opts);
                    await carregarMercado(orgId, null);
                }));
            }
            const link = element("a", "Gerir plano no painel do parceiro", "botao botao--secundario");
            link.href = "parceiro.html";
            controls.appendChild(link);
            mercado.appendChild(controls);
            try { renderFaturas(mercado, await ChurrasPlanAPI.billingFaturas(opts)); }
            catch (e) { mercado.appendChild(element("p", "Faturas indisponíveis: " + e.message)); }
            if (etapa) history.replaceState(null, "", "minha-conta.html");
        } catch (err) {
            msg.textContent = "Falha na validação da organização: " + err.message +
                ". Confirme login de proprietário e organização correta; nenhum direito foi concedido pelo navegador.";
        }
    }
    const params = new URLSearchParams(location.search);
    const orgId = params.get("organizacao_id");
    const etapa = params.get("cobranca");
    if (!await ChurrasPlanAuth.usuarioAtual().catch(() => null)) return;
    if (etapa === "cancelada") mercado.appendChild(element("p", "Checkout de mercado cancelado. Nenhum pagamento foi confirmado."));
    if (orgId && /^[1-9]\d{0,14}$/.test(orgId)) await carregarMercado(orgId, etapa);
    await carregarPessoal();
});