function authMensagem(texto, tipo = "aviso") {
    const el = document.getElementById("auth-message");
    if (el) mostrarMensagem(el, texto, tipo);
}
// Só a validação do FastAPI no campo "token" indica link cortado. Um 422 com
// texto, como a regra de senha da redefinição, mantém a mensagem da API.
function tokenDoLinkIncompleto(erro) {
    const detalhe = erro?.status === 422 ? erro.body?.detail : null;
    return Array.isArray(detalhe) && detalhe.some((item) => Array.isArray(item?.loc) && item.loc.includes("token"));
}
function parametroNext() {
    const solicitado = new URLSearchParams(location.search).get("next");
    // Entrar pelo menu público sempre abre a conta; só preservamos destinos
    // específicos quando uma página protegida os solicitou explicitamente.
    if (!solicitado || solicitado === "index.html") return "minha-conta.html";
    return ChurrasPlanAuth.destinoSeguro(solicitado, "minha-conta.html");
}
// Antes de enviar dados, espera a API acordar (no plano gratuito do Render ela
// dorme depois de 15 minutos sem uso). Se a espera passar de dois segundos,
// explica o que está acontecendo.
async function esperarApiAntesDeEnviar(botao) {
    botao?.classList.add("is-loading");
    const aviso = window.setTimeout(() => authMensagem("Conectando ao servidor. Quando ele fica um tempo sem uso, isso pode levar até um minuto.", "aviso"), 2000);
    try { await aguardarApiDisponivel(); }
    finally { window.clearTimeout(aviso); }
}
function liberarBotao(botao) {
    if (!botao) return;
    botao.disabled = false;
    botao.classList.remove("is-loading");
}
async function aposAutenticar() {
    ChurrasPlanAuth.limparCache();
    try {
        const mfa = await requisitar('/api/auth/mfa/status');
        if (mfa.ativo || mfa.obrigatorio) { irPara('seguranca.html?next=' + encodeURIComponent(parametroNext())); return; }
    } catch { /* A API continua validando o MFA em cada operação. */ }
    try { await ChurrasPlanAuth.usuarioAtual(true); await ChurrasPlanAuth.vincularPlanejamentoAtual(); } catch { /* vínculo é melhoria, não bloqueio */ }
    irPara(parametroNext());
}

document.addEventListener("DOMContentLoaded", async () => {
    const pagina = document.body.dataset.authPage, form = document.getElementById("auth-form");
    // Os formulários respondem antes de qualquer espera. Antes, a checagem de
    // sessão vinha primeiro e, com a API dormindo, o botão recarregava a página.
    let enviando = false;
    if (pagina === "login" && form) form.addEventListener("submit", async (e) => {
        e.preventDefault(); const botao = form.querySelector("button[type=submit]"); botao.disabled = true; enviando = true;
        const credenciais = { email: document.getElementById("auth-email").value.trim(), senha: document.getElementById("auth-senha").value };
        try { await esperarApiAntesDeEnviar(botao); await ChurrasPlanAPI.login(credenciais); await aposAutenticar(); }
        catch (erro) { authMensagem(erro.message, "erro"); liberarBotao(botao); enviando = false; }
    });
    if (pagina === "cadastro" && form) form.addEventListener("submit", async (e) => {
        e.preventDefault(); const botao = form.querySelector("button[type=submit]"); botao.disabled = true; enviando = true;
        const cadastro = {
            nome: document.getElementById("auth-nome").value.trim(),
            email: document.getElementById("auth-email").value.trim(),
            senha: document.getElementById("auth-senha").value,
            aceite_termos: document.getElementById("aceite-termos")?.checked === true,
            aceite_privacidade: document.getElementById("aceite-privacidade")?.checked === true,
            aceite_marketing: document.getElementById("aceite-marketing")?.checked === true,
            aceite_analytics: typeof ChurrasPlanAnalytics !== 'undefined' && ChurrasPlanAnalytics.permitido(),
            referral_codigo: (() => { try { return ChurrasPlanAnalytics.permitido() ? sessionStorage.getItem('churrasplan_referral') : null; } catch { return null; } })(),
        };
        try {
            await esperarApiAntesDeEnviar(botao);
            const resposta = await ChurrasPlanAPI.registrar(cadastro);
            ChurrasPlanAuth.limparCache();
            const usuario = await ChurrasPlanAuth.usuarioAtual(true).catch(() => null);
            if (usuario) {
                authMensagem(resposta.mensagem || "Conta criada com sucesso.", "sucesso");
                setTimeout(() => aposAutenticar(), 500);
                return;
            }
            if (resposta.dev_verification_token) {
                authMensagem("Conta criada. Confirme seu e-mail antes de entrar. Neste ambiente de desenvolvimento, use o link abaixo.", "sucesso");
                const links = document.querySelector(".auth-links");
                if (links && !links.querySelector("[data-dev-verification]")) {
                    links.insertAdjacentHTML("beforeend", `<a data-dev-verification href="verificar-email.html?token=${encodeURIComponent(resposta.dev_verification_token)}">Verificar agora</a>`);
                }
                liberarBotao(botao);
            } else {
                authMensagem(resposta.mensagem || "Conta criada. Verifique seu e-mail para ativá-la.", "sucesso");
                setTimeout(() => irPara("login.html"), 1200);
            }
        } catch (erro) { authMensagem(erro.message, "erro"); liberarBotao(botao); enviando = false; }
    });
    if (pagina === "recuperar" && form) form.addEventListener("submit", async (e) => {
        e.preventDefault(); const botao = form.querySelector("button[type=submit]"); botao.disabled = true;
        const email = document.getElementById("auth-email").value.trim();
        try {
            await esperarApiAntesDeEnviar(botao);
            const resposta = await ChurrasPlanAPI.esqueciSenha(email); authMensagem(resposta.mensagem, "sucesso");
            if (resposta.dev_token) document.getElementById("dev-link").innerHTML = `<div class="auth-links"><a href="redefinir-senha.html?token=${encodeURIComponent(resposta.dev_token)}">Abrir redefinição (desenvolvimento)</a></div>`;
        } catch (erro) { authMensagem(erro.message, "erro"); } finally { liberarBotao(botao); }
    });
    if (pagina === "redefinir" && form) form.addEventListener("submit", async (e) => {
        e.preventDefault(); const token = new URLSearchParams(location.search).get("token"), s1 = document.getElementById("auth-senha").value, s2 = document.getElementById("auth-senha2").value;
        if (!token) { authMensagem("Link de redefinição inválido.", "erro"); return; }
        if (s1 !== s2) { authMensagem("As senhas não coincidem.", "erro"); return; }
        const botao = form.querySelector("button[type=submit]"); botao.disabled = true;
        try { await esperarApiAntesDeEnviar(botao); const r = await ChurrasPlanAPI.redefinirSenha(token, s1); authMensagem(r.mensagem, "sucesso"); setTimeout(() => irPara("login.html"), 900); } catch (erro) { authMensagem(tokenDoLinkIncompleto(erro) ? "Este link de redefinição está incompleto. Peça um novo em Esqueci minha senha." : erro.message, "erro"); liberarBotao(botao); }
    });
    // Quem já tem sessão sai do login e do cadastro, a menos que já esteja
    // enviando o formulário.
    if (["login", "cadastro"].includes(pagina)) {
        const atual = await ChurrasPlanAuth.usuarioAtual().catch(() => null);
        if (atual && !enviando) { irPara(parametroNext()); return; }
    }
    if (pagina === "verificar") {
        const token = new URLSearchParams(location.search).get("token");
        if (!token) { authMensagem("Link de verificação inválido.", "erro"); return; }
        try { await esperarApiAntesDeEnviar(null); const r = await ChurrasPlanAPI.verificarEmail(token); document.getElementById("verify-title").textContent = "E-mail confirmado ✓"; document.getElementById("verify-copy").textContent = r.mensagem; authMensagem("Sua conta está pronta para os recursos avançados.", "sucesso"); }
        catch (erro) { authMensagem(""); document.getElementById("verify-title").textContent = "Não foi possível verificar"; document.getElementById("verify-copy").textContent = tokenDoLinkIncompleto(erro) ? "Este link de verificação está incompleto. Abra novamente o link enviado para o seu e-mail." : erro.message; }
    }
});
