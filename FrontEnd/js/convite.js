function conviteData(valor) {
    if (!valor) return "Data a confirmar";
    const d = new Date(valor);
    return Number.isNaN(d.getTime()) ? "Data a confirmar" : d.toLocaleString("pt-BR", { dateStyle: "full", timeStyle: "short" });
}

function chaveLocalRSVP(codigo) { return `churrasplan:rsvp:${codigo}`; }

function lerChaveRSVP(codigo) {
    try { return localStorage.getItem(chaveLocalRSVP(codigo)); } catch { return null; }
}

function salvarChaveRSVP(codigo, chave) {
    try { localStorage.setItem(chaveLocalRSVP(codigo), chave); } catch { /* navegação privada pode bloquear storage */ }
}

function removerChaveRSVP(codigo) {
    try { localStorage.removeItem(chaveLocalRSVP(codigo)); } catch { /* noop */ }
}

function novaChaveRSVP() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    if (window.crypto?.getRandomValues) {
        const bytes = new Uint8Array(24);
        window.crypto.getRandomValues(bytes);
        return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    }
    // Fallback apenas para navegadores muito antigos. A chave é de idempotência
    // da resposta e não uma credencial da conta do usuário.
    return `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`.slice(0, 48);
}

function preencherRSVP(form, dados) {
    document.getElementById("rsvp-nome").value = dados.nome || "";
    const radio = form.querySelector(`input[name="resposta"][value="${CSS.escape(dados.resposta || "")}"]`);
    if (radio) radio.checked = true;
    document.getElementById("rsvp-tipo").value = dados.tipo_convidado || "adulto";
    document.getElementById("rsvp-alcool").checked = Boolean(dados.consome_alcool);
    document.getElementById("rsvp-vegetariano").checked = Boolean(dados.vegetariano);
    document.getElementById("rsvp-vegano").checked = Boolean(dados.vegano);
    document.getElementById("rsvp-sem-bovina").checked = Boolean(dados.sem_carne_bovina);
    document.getElementById("rsvp-sem-suina").checked = Boolean(dados.sem_carne_suina);
    document.getElementById("rsvp-lactose").checked = Boolean(dados.intolerante_lactose);
    document.getElementById("rsvp-alergias").value = dados.alergias || "";
    document.getElementById("rsvp-outras").value = dados.outras_restricoes || "";
    document.getElementById("rsvp-tipo").dispatchEvent(new Event("change"));
}

document.addEventListener("DOMContentLoaded", async () => {
    const codigo = new URLSearchParams(location.search).get("codigo");
    const msg = document.getElementById("convite-mensagem");
    const form = document.getElementById("rsvp-form");
    const botao = form?.querySelector("button[type=submit]");
    let chaveResposta = lerChaveRSVP(codigo || "");
    let editando = false;

    if (!codigo) { mostrarMensagem(msg, "Convite inválido.", "erro"); return; }

    try {
        const c = await ChurrasPlanAPI.convitePublico(codigo);
        document.title = `${c.nome_churrasco || "Churrasco"} — ChurrasPlan`;
        document.getElementById("convite-evento").innerHTML = `<span class="eyebrow"><span></span>VOCÊ FOI CONVIDADO</span><h1>${escaparHTML(c.nome_churrasco || "Churrasco")}</h1><p>${escaparHTML(conviteData(c.data_evento))} · ${formatarNumero(c.duracao_horas, Number.isInteger(c.duracao_horas) ? 0 : 1)}h${c.organizador ? ` · por ${escaparHTML(c.organizador)}` : ""}</p>`;
        form.style.display = "grid";
    } catch (erro) {
        mostrarMensagem(msg, erro.message, "erro");
        return;
    }

    document.getElementById("rsvp-tipo").onchange = (e) => {
        const alcool = document.getElementById("rsvp-alcool");
        if (e.target.value === "crianca") { alcool.checked = false; alcool.disabled = true; }
        else alcool.disabled = false;
    };
    document.getElementById("rsvp-vegano").onchange = (e) => {
        if (e.target.checked) document.getElementById("rsvp-vegetariano").checked = false;
    };

    // Se este navegador já respondeu ao convite, recupera e permite editar a
    // resposta. Um 404 apenas descarta uma chave local obsoleta.
    if (chaveResposta) {
        try {
            const existente = await ChurrasPlanAPI.respostaConvite(codigo, chaveResposta);
            preencherRSVP(form, existente);
            editando = true;
            if (botao) botao.textContent = "Atualizar resposta";
            mostrarMensagem(msg, "Sua resposta anterior foi carregada. Você pode atualizá-la.", "sucesso");
        } catch (erro) {
            if (erro.status === 404) {
                removerChaveRSVP(codigo);
                chaveResposta = null;
            } else {
                mostrarMensagem(msg, "Não foi possível recuperar sua resposta anterior, mas você ainda pode tentar novamente.", "erro");
            }
        }
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (botao) botao.disabled = true;
        mostrarMensagem(msg, "", "sucesso");
        try {
            const resposta = form.querySelector('input[name="resposta"]:checked')?.value;
            if (!resposta) throw new Error("Informe se você vai ao churrasco.");

            // A chave é persistida ANTES da chamada. Se a rede cair depois de o
            // servidor salvar, o próximo envio reapresenta a mesma chave e vira
            // update em vez de um segundo convidado.
            if (!chaveResposta) {
                chaveResposta = novaChaveRSVP();
                salvarChaveRSVP(codigo, chaveResposta);
            }

            const salvo = await ChurrasPlanAPI.responderConvite(codigo, {
                chave_resposta: chaveResposta,
                nome: document.getElementById("rsvp-nome").value.trim(),
                resposta,
                tipo_convidado: document.getElementById("rsvp-tipo").value,
                consome_alcool: document.getElementById("rsvp-alcool").checked,
                vegetariano: document.getElementById("rsvp-vegetariano").checked,
                vegano: document.getElementById("rsvp-vegano").checked,
                sem_carne_bovina: document.getElementById("rsvp-sem-bovina").checked,
                sem_carne_suina: document.getElementById("rsvp-sem-suina").checked,
                intolerante_lactose: document.getElementById("rsvp-lactose").checked,
                alergias: document.getElementById("rsvp-alergias").value.trim() || null,
                outras_restricoes: document.getElementById("rsvp-outras").value.trim() || null,
            });
            if (salvo?.chave_resposta) {
                chaveResposta = salvo.chave_resposta;
                salvarChaveRSVP(codigo, chaveResposta);
            }
            editando = true;
            if (botao) botao.textContent = "Atualizar resposta";
            mostrarMensagem(msg, "Resposta salva ✓ Você pode voltar a este link para alterá-la depois.", "sucesso");
        } catch (erro) {
            mostrarMensagem(msg, erro.message, "erro");
        } finally {
            if (botao) botao.disabled = false;
        }
    });
});
