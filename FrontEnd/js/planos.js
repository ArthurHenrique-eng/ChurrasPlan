/** Vitrine pública de assinaturas. Valores vêm do Stripe Test, jamais são inventados. */
(() => {
    "use strict";
    const el = id => document.getElementById(id);
    let precos = { usuario: [], parceiro: [] };
    let usuario = null;
    const formato = centavos => (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    const periodicidade = () => el("planos-periodo").value;
    const aviso = (mensagem, erro = true) => {
        const box = el("planos-mensagem");
        box.hidden = false; box.textContent = mensagem;
        box.style.borderColor = erro ? "#d88d78" : "#a6bba5";
        box.scrollIntoView({ behavior: "smooth", block: "nearest" });
    };
    const variaveisPreco = {
        premium: { mensal: "STRIPE_PRICE_USER_PREMIUM_MONTHLY", anual: "STRIPE_PRICE_USER_PREMIUM_YEARLY" },
        pro: { mensal: "STRIPE_PRICE_PRO", anual: "STRIPE_PRICE_PRO_YEARLY" },
        business: { mensal: "STRIPE_PRICE_BUSINESS", anual: "STRIPE_PRICE_BUSINESS_YEARLY" }
    };
    const catalogoFalhou = { usuario: false, parceiro: false };
    function mostrar() {
        for (const plano of ["premium", "pro", "business"]) {
            const publico = plano === "premium" ? "usuario" : "parceiro";
            const achado = precos[publico].find(item => item.plano === plano && item.periodicidade === periodicidade());
            const btn = document.querySelector('[data-plano="' + plano + '"]');
            btn.disabled = !achado;
            el("preco-" + plano).textContent = achado
                ? formato(achado.centavos) + (periodicidade() === "mensal" ? " / mês" : " / ano")
                : "Indisponível no teste";
            const nota = el("aviso-" + plano);
            if (achado) {
                nota.textContent = "Preço validado no Stripe Test. Nenhuma cobrança real.";
            } else if (catalogoFalhou[publico]) {
                nota.textContent = "Falha ao consultar o Stripe Test. Verifique chave sk_test_, Price ID e logs da API.";
            } else {
                nota.textContent = "Configuração pendente no backend: verifique BILLING_ENABLED=true, sk_test_, whsec_ e " +
                    variaveisPreco[plano][periodicidade()] + " no .env.";
            }
        }
    }
    const chave = () => (window.crypto && crypto.randomUUID ? crypto.randomUUID() :
        "teste-" + Date.now() + "-" + Math.random().toString(36).slice(2));
    function voltarAoLogin(plano) {
        const next = "planos.html?contratar=" + encodeURIComponent(plano) + "&periodicidade=" + encodeURIComponent(periodicidade());
        location.assign(ChurrasPlanAuth.urlLogin(next));
    }
    async function assinar(plano, btn) {
        if (!usuario) { voltarAoLogin(plano); return; }
        btn.disabled = true;
        try {
            const periodo = periodicidade();
            if (plano === "premium") {
                const resultado = await ChurrasPlanAPI.billingUsuarioCheckout({
                    plano: "premium", periodicidade: periodo, chave_idempotencia: chave()
                });
                location.assign(resultado.checkout_url);
                return;
            }
            if (usuario.papel === "usuario") {
                if (!window.confirm("Ativar gratuitamente sua área de mercado parceiro para contratar o plano?")) return;
                await ChurrasPlanAPI.ativarParceiro();
                ChurrasPlanAuth.limparCache();
                usuario = await ChurrasPlanAuth.usuarioAtual(true);
            }
            const orgs = await ChurrasPlanAPI.organizacoesParceiro();
            const proprias = orgs.filter(o => o.papel === "proprietario");
            if (proprias.length !== 1) {
                aviso("Selecione primeiro sua organização (como proprietário) na Área do Parceiro para assinar.");
                location.assign("parceiro.html?assinar=" + encodeURIComponent(plano));
                return;
            }
            ChurrasPlanAPI.definirOrganizacaoAtiva(proprias[0].id);
            const pedido = await ChurrasPlanAPI.billingCheckout({
                plano, periodicidade: periodo, chave_idempotencia: chave()
            });
            location.assign(pedido.checkout_url);
        } catch (error) {
            aviso(error.message || "Não foi possível iniciar o checkout de teste.");
        } finally {
            btn.disabled = false;
        }
    }
    document.addEventListener("DOMContentLoaded", async () => {
        el("planos-periodo").addEventListener("change", mostrar);
        document.querySelectorAll("[data-plano]").forEach(btn => btn.addEventListener("click", () => assinar(btn.dataset.plano, btn)));
        const params = new URLSearchParams(location.search);
        if (params.get("periodicidade") === "anual") el("planos-periodo").value = "anual";
        if (params.get("assinatura") === "cancelada") aviso("Checkout cancelado; sua assinatura não foi alterada.", false);
        const [u, p, m] = await Promise.allSettled([
            ChurrasPlanAuth.usuarioAtual(),
            ChurrasPlanAPI.billingUsuarioCatalogo(),
            ChurrasPlanAPI.billingPlanosPublicos(),
        ]);
        usuario = u.status === "fulfilled" ? u.value : null;
        precos.usuario = p.status === "fulfilled" ? (p.value.planos || []) : [];
        precos.parceiro = m.status === "fulfilled" ? (m.value.planos || []) : [];
        catalogoFalhou.usuario = p.status === "rejected";
        catalogoFalhou.parceiro = m.status === "rejected";
        mostrar();
        if (params.has("contratar") && usuario) aviso("Você já está conectado. Escolha o plano para abrir o Checkout Stripe Test.", false);
        if (p.status === "rejected" || m.status === "rejected")
            aviso("A consulta aos preços de teste falhou; confira a conexão e as configurações Stripe.");
    });
})();
