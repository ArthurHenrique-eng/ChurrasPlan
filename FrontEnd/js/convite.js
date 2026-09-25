function conviteEscaparHTML(valor) {
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function conviteMensagem(texto, tipo = "aviso") {
    const el = document.getElementById("convite-mensagem");
    if (!el) return;
    if (!texto) {
        el.style.display = "none";
        el.textContent = "";
        el.className = "mensagem auth-message";
        return;
    }
    el.textContent = texto;
    el.className = `mensagem auth-message mensagem--${tipo}`;
    el.style.display = "block";
}

function conviteData(valor) {
    if (!valor) return "Data a confirmar";
    const d = new Date(valor);
    return Number.isNaN(d.getTime())
        ? "Data a confirmar"
        : d.toLocaleString("pt-BR", {
            dateStyle: "full",
            timeStyle: "short",
        });
}

function conviteDuracao(valor) {
    const n = Number(valor);
    if (!Number.isFinite(n)) return "";
    return Number.isInteger(n)
        ? String(n)
        : n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
}

function chaveLocalRSVP(codigo) {
    return `churrasplan:rsvp:${codigo}`;
}

function lerChaveRSVP(codigo) {
    try {
        return localStorage.getItem(chaveLocalRSVP(codigo));
    } catch {
        return null;
    }
}

function salvarChaveRSVP(codigo, chave) {
    try {
        localStorage.setItem(chaveLocalRSVP(codigo), chave);
    } catch {
        // Navegação privada pode bloquear storage.
    }
}

function removerChaveRSVP(codigo) {
    try {
        localStorage.removeItem(chaveLocalRSVP(codigo));
    } catch {
        // noop
    }
}

function novaChaveRSVP() {
    if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
    }
    if (window.crypto?.getRandomValues) {
        const bytes = new Uint8Array(24);
        window.crypto.getRandomValues(bytes);
        return Array.from(
            bytes,
            (b) => b.toString(16).padStart(2, "0"),
        ).join("");
    }
    return (
        `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
    ).slice(0, 48);
}

function preencherRSVP(form, dados) {
    document.getElementById("rsvp-nome").value = dados.nome || "";

    const valorResposta = ["confirmado", "talvez", "nao"].includes(dados.resposta)
        ? dados.resposta
        : null;
    if (valorResposta) {
        const radio = form.querySelector(
            `input[name="resposta"][value="${valorResposta}"]`,
        );
        if (radio) radio.checked = true;
    }

    document.getElementById("rsvp-tipo").value =
        dados.tipo_convidado || "adulto";
    document.getElementById("rsvp-alcool").checked =
        Boolean(dados.consome_alcool);
    document.getElementById("rsvp-vegetariano").checked =
        Boolean(dados.vegetariano);
    document.getElementById("rsvp-vegano").checked =
        Boolean(dados.vegano);
    document.getElementById("rsvp-sem-bovina").checked =
        Boolean(dados.sem_carne_bovina);
    document.getElementById("rsvp-sem-suina").checked =
        Boolean(dados.sem_carne_suina);
    document.getElementById("rsvp-lactose").checked =
        Boolean(dados.intolerante_lactose);
    document.getElementById("rsvp-alergias").value =
        dados.alergias || "";
    document.getElementById("rsvp-outras").value =
        dados.outras_restricoes || "";

    document.getElementById("rsvp-tipo").dispatchEvent(
        new Event("change"),
    );
}

function mostrarFalhaConvite(mensagem) {
    const evento = document.getElementById("convite-evento");
    evento.innerHTML = `
        <span class="eyebrow"><span></span>CONVITE INDISPONÍVEL</span>
        <h1>Não foi possível abrir este convite.</h1>
        <p>${conviteEscaparHTML(mensagem)}</p>
    `;
    conviteMensagem(
        "Confira se o link foi copiado por completo e se o servidor do ChurrasPlan está acessível.",
        "erro",
    );
}

document.addEventListener("DOMContentLoaded", async () => {
    const codigo = new URLSearchParams(location.search)
        .get("codigo")
        ?.trim();
    const form = document.getElementById("rsvp-form");
    const botao = form?.querySelector('button[type="submit"]');
    let chaveResposta = codigo ? lerChaveRSVP(codigo) : null;

    if (!codigo) {
        mostrarFalhaConvite("O link não possui um código de convite válido.");
        return;
    }

    try {
        const c = await ChurrasPlanAPI.convitePublico(codigo);
        document.title =
            `${c.nome_churrasco || "Churrasco"} — Convite ChurrasPlan`;

        const partes = [
            conviteData(c.data_evento),
            c.duracao_horas != null
                ? `${conviteDuracao(c.duracao_horas)}h de duração`
                : null,
            c.organizador
                ? `Organizado por ${c.organizador}`
                : null,
        ].filter(Boolean);

        document.getElementById("convite-evento").innerHTML = `
            <span class="eyebrow"><span></span>VOCÊ FOI CONVIDADO</span>
            <h1>${conviteEscaparHTML(c.nome_churrasco || "Churrasco")}</h1>
            <p>${partes.map(conviteEscaparHTML).join(" · ")}</p>
        `;

        form.hidden = false;
    } catch (erro) {
        mostrarFalhaConvite(
            erro?.message || "Não foi possível consultar os dados do convite.",
        );
        return;
    }

    const tipo = document.getElementById("rsvp-tipo");
    tipo.addEventListener("change", (event) => {
        const alcool = document.getElementById("rsvp-alcool");
        if (event.target.value === "crianca") {
            alcool.checked = false;
            alcool.disabled = true;
        } else {
            alcool.disabled = false;
        }
    });
    tipo.dispatchEvent(new Event("change"));

    document.getElementById("rsvp-vegano").addEventListener(
        "change",
        (event) => {
            if (event.target.checked) {
                document.getElementById("rsvp-vegetariano").checked = false;
            }
        },
    );

    document.getElementById("rsvp-vegetariano").addEventListener(
        "change",
        (event) => {
            if (event.target.checked) {
                document.getElementById("rsvp-vegano").checked = false;
            }
        },
    );

    if (chaveResposta) {
        try {
            const existente = await ChurrasPlanAPI.respostaConvite(
                codigo,
                chaveResposta,
            );
            preencherRSVP(form, existente);
            if (botao) botao.textContent = "Atualizar resposta";
            conviteMensagem(
                "Sua resposta anterior foi carregada. Você pode alterá-la e enviar novamente.",
                "sucesso",
            );
        } catch (erro) {
            if (erro.status === 404) {
                removerChaveRSVP(codigo);
                chaveResposta = null;
            } else {
                conviteMensagem(
                    "Não foi possível recuperar sua resposta anterior. Você ainda pode responder novamente.",
                    "aviso",
                );
            }
        }
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (botao) {
            botao.disabled = true;
            botao.textContent = chaveResposta
                ? "Atualizando..."
                : "Enviando...";
        }

        conviteMensagem("");

        try {
            const resposta = form.querySelector(
                'input[name="resposta"]:checked',
            )?.value;

            if (!resposta) {
                throw new Error("Informe se você vai ao churrasco.");
            }

            const nome = document.getElementById("rsvp-nome")
                .value
                .trim();
            if (nome.length < 2) {
                throw new Error("Informe seu nome.");
            }

            if (!chaveResposta) {
                chaveResposta = novaChaveRSVP();
                salvarChaveRSVP(codigo, chaveResposta);
            }

            const salvo = await ChurrasPlanAPI.responderConvite(
                codigo,
                {
                    chave_resposta: chaveResposta,
                    nome,
                    resposta,
                    tipo_convidado: tipo.value,
                    consome_alcool:
                        document.getElementById("rsvp-alcool").checked,
                    vegetariano:
                        document.getElementById("rsvp-vegetariano").checked,
                    vegano:
                        document.getElementById("rsvp-vegano").checked,
                    sem_carne_bovina:
                        document.getElementById("rsvp-sem-bovina").checked,
                    sem_carne_suina:
                        document.getElementById("rsvp-sem-suina").checked,
                    intolerante_lactose:
                        document.getElementById("rsvp-lactose").checked,
                    alergias:
                        document.getElementById("rsvp-alergias")
                            .value
                            .trim() || null,
                    outras_restricoes:
                        document.getElementById("rsvp-outras")
                            .value
                            .trim() || null,
                },
            );

            if (salvo?.chave_resposta) {
                chaveResposta = salvo.chave_resposta;
                salvarChaveRSVP(codigo, chaveResposta);
            }

            if (botao) botao.textContent = "Atualizar resposta";

            const mensagem = resposta === "confirmado"
                ? "Presença confirmada. Obrigado por responder!"
                : resposta === "talvez"
                    ? "Resposta salva como talvez. Você pode voltar e atualizar depois."
                    : "Resposta salva. O organizador será informado.";

            conviteMensagem(mensagem, "sucesso");
        } catch (erro) {
            conviteMensagem(
                erro?.message || "Não foi possível salvar sua resposta.",
                "erro",
            );
            if (botao) {
                botao.textContent = chaveResposta
                    ? "Atualizar resposta"
                    : "Enviar resposta";
            }
        } finally {
            if (botao) botao.disabled = false;
        }
    });
});
