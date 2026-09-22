function authMensagem(texto, tipo = "aviso") {
    const el = document.getElementById("auth-message");
    if (el) mostrarMensagem(el, texto, tipo);
}
function parametroNext() { return ChurrasPlanAuth.destinoSeguro(new URLSearchParams(location.search).get("next"), "minha-conta.html"); }
async function aposAutenticar() {
    ChurrasPlanAuth.limparCache();
    try { await ChurrasPlanAuth.usuarioAtual(true); await ChurrasPlanAuth.vincularPlanejamentoAtual(); } catch { /* vínculo é melhoria, não bloqueio */ }
    irPara(parametroNext());
}

document.addEventListener("DOMContentLoaded", async () => {
    const pagina = document.body.dataset.authPage, form = document.getElementById("auth-form");
    if (["login", "cadastro"].includes(pagina)) {
        const atual = await ChurrasPlanAuth.usuarioAtual().catch(() => null);
        if (atual) { irPara(parametroNext()); return; }
    }
    if (pagina === "login" && form) form.addEventListener("submit", async (e) => {
        e.preventDefault(); const botao = form.querySelector("button[type=submit]"); botao.disabled = true;
        try { await ChurrasPlanAPI.login({ email: document.getElementById("auth-email").value.trim(), senha: document.getElementById("auth-senha").value }); await aposAutenticar(); }
        catch (erro) { authMensagem(erro.message, "erro"); botao.disabled = false; }
    });
    if (pagina === "cadastro" && form) form.addEventListener("submit", async (e) => {
        e.preventDefault(); const botao = form.querySelector("button[type=submit]"); botao.disabled = true;
        try {
            const resposta = await ChurrasPlanAPI.registrar({
                nome: document.getElementById("auth-nome").value.trim(),
                email: document.getElementById("auth-email").value.trim(),
                senha: document.getElementById("auth-senha").value,
                aceite_termos: document.getElementById("aceite-termos")?.checked === true,
                aceite_privacidade: document.getElementById("aceite-privacidade")?.checked === true,
                aceite_marketing: document.getElementById("aceite-marketing")?.checked === true,
            });
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
                botao.disabled = false;
            } else {
                authMensagem(resposta.mensagem || "Conta criada. Verifique seu e-mail para ativá-la.", "sucesso");
                setTimeout(() => irPara("login.html"), 1200);
            }
        } catch (erro) { authMensagem(erro.message, "erro"); botao.disabled = false; }
    });
    if (pagina === "recuperar" && form) form.addEventListener("submit", async (e) => {
        e.preventDefault(); const botao = form.querySelector("button[type=submit]"); botao.disabled = true;
        try {
            const resposta = await ChurrasPlanAPI.esqueciSenha(document.getElementById("auth-email").value.trim()); authMensagem(resposta.mensagem, "sucesso");
            if (resposta.dev_token) document.getElementById("dev-link").innerHTML = `<div class="auth-links"><a href="redefinir-senha.html?token=${encodeURIComponent(resposta.dev_token)}">Abrir redefinição (desenvolvimento)</a></div>`;
        } catch (erro) { authMensagem(erro.message, "erro"); } finally { botao.disabled = false; }
    });
    if (pagina === "redefinir" && form) form.addEventListener("submit", async (e) => {
        e.preventDefault(); const token = new URLSearchParams(location.search).get("token"), s1 = document.getElementById("auth-senha").value, s2 = document.getElementById("auth-senha2").value;
        if (!token) { authMensagem("Link de redefinição inválido.", "erro"); return; }
        if (s1 !== s2) { authMensagem("As senhas não coincidem.", "erro"); return; }
        try { const r = await ChurrasPlanAPI.redefinirSenha(token, s1); authMensagem(r.mensagem, "sucesso"); setTimeout(() => irPara("login.html"), 900); } catch (erro) { authMensagem(erro.message, "erro"); }
    });
    if (pagina === "verificar") {
        const token = new URLSearchParams(location.search).get("token");
        if (!token) { authMensagem("Link de verificação inválido.", "erro"); return; }
        try { const r = await ChurrasPlanAPI.verificarEmail(token); document.getElementById("verify-title").textContent = "E-mail confirmado ✓"; document.getElementById("verify-copy").textContent = r.mensagem; authMensagem("Sua conta está pronta para os recursos avançados.", "sucesso"); }
        catch (erro) { document.getElementById("verify-title").textContent = "Não foi possível verificar"; document.getElementById("verify-copy").textContent = erro.message; }
    }
});
