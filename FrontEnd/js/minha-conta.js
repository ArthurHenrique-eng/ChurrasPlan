function fmtData(valor) { if (!valor) return "Sem data definida"; const d = new Date(valor); return Number.isNaN(d.getTime()) ? "Sem data definida" : d.toLocaleString("pt-BR", { dateStyle: "medium", timeStyle: "short" }); }

function criarDialogExclusaoConta() {
    if (document.getElementById("dialog-excluir-conta")) return;
    const dialog = document.createElement("dialog");
    dialog.id = "dialog-excluir-conta";
    dialog.className = "danger-dialog";
    dialog.innerHTML = `<form method="dialog" class="price-dialog__box danger-dialog__box">
        <button value="cancel" class="dialog-close" aria-label="Fechar">×</button>
        <span class="eyebrow"><span></span>EXCLUSÃO DEFINITIVA</span>
        <h2>Excluir sua conta?</h2>
        <p>Seus churrascos privados, sessões e dados pessoais vinculados à conta serão removidos. Esta ação não pode ser desfeita.</p>
        <label class="campo"><span>Confirme sua senha</span><input id="exclusao-senha" type="password" autocomplete="current-password" required minlength="8"></label>
        <label class="campo"><span>Digite EXCLUIR</span><input id="exclusao-confirmacao" type="text" autocomplete="off" required></label>
        <div class="dialog-actions"><button value="cancel" class="botao botao--secundario">Cancelar</button><button value="confirm" class="botao botao--perigo">Excluir definitivamente</button></div>
    </form>`;
    document.body.appendChild(dialog);
}

async function solicitarExclusaoConta() {
    criarDialogExclusaoConta();
    const dialog = document.getElementById("dialog-excluir-conta");
    document.getElementById("exclusao-senha").value = "";
    document.getElementById("exclusao-confirmacao").value = "";
    dialog.showModal();
    const resultado = await new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue), { once: true }));
    if (resultado !== "confirm") return;
    const confirmacao = document.getElementById("exclusao-confirmacao").value.trim().toUpperCase();
    if (confirmacao !== "EXCLUIR") throw new Error("Digite EXCLUIR para confirmar a exclusão.");
    await ChurrasPlanAPI.excluirMinhaConta(document.getElementById("exclusao-senha").value);
    EstadoChurrasco.limpar();
    ChurrasPlanAuth.limparCache();
    irPara("index.html");
}

async function configurarPrivacidadeConta(usuario) {
    const admin = document.getElementById("link-admin");
    if (admin) admin.hidden = usuario.papel !== "admin";
    const checkbox = document.getElementById("marketing-optin");
    try {
        const consentimentos = await ChurrasPlanAPI.meusConsentimentos();
        const marketing = consentimentos.find((c) => c.tipo === "marketing");
        checkbox.checked = marketing?.concedido === true;
    } catch { checkbox.checked = false; }
    checkbox.addEventListener("change", async () => {
        checkbox.disabled = true;
        try { await ChurrasPlanAPI.atualizarMarketing(checkbox.checked); mostrarMensagem(document.getElementById("conta-mensagem"), "Preferência de comunicação atualizada.", "sucesso"); }
        catch (e) { checkbox.checked = !checkbox.checked; mostrarMensagem(document.getElementById("conta-mensagem"), e.message, "erro"); }
        finally { checkbox.disabled = false; }
    });
    document.getElementById("exportar-dados").addEventListener("click", async (e) => {
        const botao = e.currentTarget; botao.disabled = true;
        try {
            const dados = await ChurrasPlanAPI.exportarMeusDados();
            const blob = new Blob([JSON.stringify(dados, null, 2)], { type: "application/json;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a"); a.href = url; a.download = `churrasplan-dados-${new Date().toISOString().slice(0,10)}.json`; a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (erro) { mostrarMensagem(document.getElementById("conta-mensagem"), erro.message, "erro"); }
        finally { botao.disabled = false; }
    });
    document.getElementById("excluir-conta").addEventListener("click", () => solicitarExclusaoConta().catch((e) => mostrarMensagem(document.getElementById("conta-mensagem"), e.message, "erro")));
}
async function abrirHistorico(id) {
    const dados = await ChurrasPlanAPI.obterChurrasco(id); EstadoChurrasco.carregarResultadoSalvo(dados); irPara("resultado.html");
}
async function repetirHistorico(id, botao) {
    botao.disabled = true; const antigo = botao.textContent; botao.textContent = "Criando...";
    try { const dados = await ChurrasPlanAPI.repetirChurrasco(id, {}); EstadoChurrasco.carregarResultadoSalvo(dados); irPara("resultado.html"); }
    catch (erro) { mostrarMensagem(document.getElementById("conta-mensagem"), erro.message, "erro"); botao.disabled = false; botao.textContent = antigo; }
}

document.addEventListener("DOMContentLoaded", async () => {
    const usuario = await ChurrasPlanAuth.usuarioAtual().catch(() => null);
    if (!usuario) { irPara(ChurrasPlanAuth.urlLogin("minha-conta.html")); return; }
    document.getElementById("conta-saudacao").textContent = `Olá, ${usuario.nome.split(" ")[0]}.`;
    document.getElementById("conta-perfil").innerHTML = `<strong>${escaparHTML(usuario.nome)}</strong><p class="texto-suave">${escaparHTML(usuario.email)}</p><div class="restriction-chips" style="margin-top:10px"><span>${escaparHTML(usuario.papel)}</span>${usuario.email_verificado_em ? '<span>e-mail verificado</span>' : '<span>verificação pendente</span>'}</div>`;
    try { const assinatura = await ChurrasPlanAPI.minhaAssinatura(); document.getElementById("conta-plano").innerHTML = `<strong>Plano ${escaparHTML(assinatura.plano || usuario.plano)}</strong><p>${assinatura.pagamentos_habilitados ? "Assinatura ativa." : "Pagamentos ainda não estão habilitados nesta versão."}</p>`; } catch { document.getElementById("conta-plano").textContent = `Plano ${usuario.plano}`; }
    await configurarPrivacidadeConta(usuario);
    try {
        const historico = await ChurrasPlanAPI.meusChurrascos(); const lista = document.getElementById("historico-lista");
        lista.innerHTML = historico.length ? historico.map((c) => {
            const custo = c.custo_total_estimado == null
                ? "sem preços cadastrados"
                : `${formatarMoeda(c.custo_total_estimado)}${c.estimativa_precos_completa ? "" : " (parcial)"}`;
            return `<article class="history-card"><div><h3>${escaparHTML(c.nome || "Churrasco")}</h3><p>${fmtData(c.data_evento)} · ${c.total_pessoas} pessoa(s) · ${custo}</p></div><div class="history-actions"><button class="botao botao--secundario" type="button" data-open="${c.id}">Abrir</button><button class="botao botao--primario" type="button" data-repeat="${c.id}">Repetir</button></div></article>`;
        }).join("") : `<div class="empty-state">Você ainda não tem churrascos salvos. Quando criar um planejamento logado, ele aparecerá aqui.</div>`;
        lista.querySelectorAll("[data-open]").forEach((b) => b.onclick = () => abrirHistorico(b.dataset.open).catch((e) => mostrarMensagem(document.getElementById("conta-mensagem"), e.message, "erro")));
        lista.querySelectorAll("[data-repeat]").forEach((b) => b.onclick = () => repetirHistorico(b.dataset.repeat, b));
    } catch (erro) { mostrarMensagem(document.getElementById("conta-mensagem"), erro.message, "erro"); }
    document.getElementById("logout").onclick = async () => { try { await ChurrasPlanAPI.logout(); } finally { ChurrasPlanAuth.limparCache(); irPara("index.html"); } };
    document.getElementById("continuar-atual").onclick = () => { const e = EstadoChurrasco.obter(); irPara(({ planejamento:"planejamento.html", carnes:"carnes.html", bebidas:"bebidas.html", extras:"extras.html", resultado:"resultado.html" })[e.etapa_atual] || "planejamento.html"); };
});
