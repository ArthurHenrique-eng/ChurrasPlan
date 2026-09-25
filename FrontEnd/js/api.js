const TEMPO_LIMITE_API_MS = 15000;

function lerCookie(nome) {
    const prefixo = `${encodeURIComponent(nome)}=`;
    const parte = document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith(prefixo));
    return parte ? decodeURIComponent(parte.slice(prefixo.length)) : null;
}

async function requisitar(caminho, opcoes = {}) {
    const controller = new AbortController();
    const { headers: headersInformados = {}, signal: sinalExterno, ...restante } = opcoes;
    const timer = window.setTimeout(() => controller.abort(), TEMPO_LIMITE_API_MS);
    const metodo = String(restante.method || "GET").toUpperCase();

    if (sinalExterno) {
        if (sinalExterno.aborted) controller.abort();
        else sinalExterno.addEventListener("abort", () => controller.abort(), { once: true });
    }

    const headers = {
        Accept: "application/json",
        ...(restante.body != null ? { "Content-Type": "application/json" } : {}),
        ...headersInformados,
    };
    if (!["GET", "HEAD", "OPTIONS"].includes(metodo)) {
        const csrf = lerCookie("churrasplan_csrf");
        if (csrf && !headers["X-CSRF-Token"]) headers["X-CSRF-Token"] = csrf;
    }

    try {
        const resposta = await fetch(`${API_BASE_URL}${caminho}`, {
            ...restante,
            headers,
            credentials: "include",
            signal: controller.signal,
        });

        let corpo = null;
        try { corpo = await resposta.json(); } catch { /* resposta sem JSON */ }

        if (!resposta.ok) {
            const detalhe = corpo && corpo.detail ? corpo.detail : `Erro ${resposta.status}`;
            const erro = new Error(typeof detalhe === "string" ? detalhe : JSON.stringify(detalhe));
            erro.status = resposta.status;
            erro.body = corpo;
            throw erro;
        }
        return corpo;
    } catch (erro) {
        if (erro.name === "AbortError") {
            const timeout = new Error("A API demorou demais para responder. Tente novamente.");
            timeout.status = 408;
            throw timeout;
        }
        if (erro instanceof TypeError) {
            const rede = new Error("Não foi possível conectar à API do ChurrasPlan.");
            rede.cause = erro;
            throw rede;
        }
        throw erro;
    } finally {
        window.clearTimeout(timer);
    }
}

function queryString(parametros = {}) {
    const q = new URLSearchParams();
    Object.entries(parametros).forEach(([chave, valor]) => {
        if (valor !== null && valor !== undefined && valor !== "") q.set(chave, String(valor));
    });
    const texto = q.toString();
    return texto ? `?${texto}` : "";
}

const ChurrasPlanAPI = {
    calcularCarnes(payload, opcoes = {}) { return requisitar("/api/calculadora/carnes", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    calcularBebidas(payload, opcoes = {}) { return requisitar("/api/calculadora/bebidas", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    calcularExtras(payload, opcoes = {}) { return requisitar("/api/calculadora/extras", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },

    criarChurrasco(payload, opcoes = {}) { return requisitar("/api/churrascos", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    obterChurrasco(id, opcoes = {}) { return requisitar(`/api/churrascos/${id}`, opcoes); },
    atualizarChurrasco(id, payload, opcoes = {}) { return requisitar(`/api/churrascos/${id}`, { ...opcoes, method: "PUT", body: JSON.stringify(payload) }); },
    meusChurrascos(opcoes = {}) { return requisitar("/api/churrascos/meus", opcoes); },
    repetirChurrasco(id, payload = {}, opcoes = {}) { return requisitar(`/api/churrascos/${id}/repetir`, { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    vincularChurrasco(id, chaveCliente, opcoes = {}) { return requisitar(`/api/churrascos/${id}/vincular`, { ...opcoes, method: "POST", body: JSON.stringify({ chave_cliente: chaveCliente }) }); },
    atualizarDivisao(id, dividirEntre, opcoes = {}) { return requisitar(`/api/churrascos/${id}/divisao`, { ...opcoes, method: "PATCH", body: JSON.stringify({ dividir_entre: dividirEntre }) }); },

    obterListaCompras(id, opcoes = {}) { return requisitar(`/api/lista-compras/${id}`, opcoes); },
    atualizarItemListaCompras(id, payloadOuComprado, opcoes = {}) {
        const payload = typeof payloadOuComprado === "boolean" ? { comprado: payloadOuComprado } : payloadOuComprado;
        return requisitar(`/api/lista-compras/item/${id}`, { ...opcoes, method: "PUT", body: JSON.stringify(payload) });
    },

    registrar(payload, opcoes = {}) { return requisitar("/api/auth/register", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    login(payload, opcoes = {}) { return requisitar("/api/auth/login", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    logout(opcoes = {}) { return requisitar("/api/auth/logout", { ...opcoes, method: "POST" }); },
    usuarioAtual(opcoes = {}) { return requisitar("/api/auth/me", opcoes); },
    verificarEmail(token, opcoes = {}) { return requisitar("/api/auth/verify-email", { ...opcoes, method: "POST", body: JSON.stringify({ token }) }); },
    esqueciSenha(email, opcoes = {}) { return requisitar("/api/auth/forgot-password", { ...opcoes, method: "POST", body: JSON.stringify({ email }) }); },
    redefinirSenha(token, novaSenha, opcoes = {}) { return requisitar("/api/auth/reset-password", { ...opcoes, method: "POST", body: JSON.stringify({ token, nova_senha: novaSenha }) }); },

    criarConvite(churrascoId, opcoes = {}) { return requisitar(`/api/convites/churrasco/${churrascoId}`, { ...opcoes, method: "POST" }); },
    resumoConvite(churrascoId, opcoes = {}) { return requisitar(`/api/convites/churrasco/${churrascoId}/resumo`, opcoes); },
    aplicarConfirmados(churrascoId, opcoes = {}) { return requisitar(`/api/convites/churrasco/${churrascoId}/aplicar-confirmados`, { ...opcoes, method: "POST" }); },
    convitePublico(codigo, opcoes = {}) { return requisitar(`/api/convites/publico/${encodeURIComponent(codigo)}`, opcoes); },
    respostaConvite(codigo, chave, opcoes = {}) { return requisitar(`/api/convites/publico/${encodeURIComponent(codigo)}/resposta/${encodeURIComponent(chave)}`, opcoes); },
    responderConvite(codigo, payload, opcoes = {}) { return requisitar(`/api/convites/publico/${encodeURIComponent(codigo)}/responder`, { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },

    listarProdutos(parametros = {}, opcoes = {}) { return requisitar(`/api/produtos${queryString(parametros)}`, opcoes); },

    ativarParceiro(opcoes = {}) { return requisitar("/api/parceiro/ativar", { ...opcoes, method: "POST" }); },
    dashboardParceiro(opcoes = {}) { return requisitar("/api/parceiro/dashboard", opcoes); },
    estabelecimentosParceiro(opcoes = {}) { return requisitar("/api/parceiro/estabelecimentos", opcoes); },
    criarEstabelecimento(payload, opcoes = {}) { return requisitar("/api/parceiro/estabelecimentos", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    produtosParceiro(opcoes = {}) { return requisitar("/api/parceiro/produtos", opcoes); },
    criarProdutoComercial(payload, opcoes = {}) { return requisitar("/api/parceiro/produtos", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    cadastrarPrecoParceiro(payload, opcoes = {}) { return requisitar("/api/parceiro/precos", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },

    configOndeComprar(opcoes = {}) { return requisitar("/api/onde-comprar/config", opcoes); },
    autocompleteEndereco(texto, latitude = null, longitude = null, limite = 6, opcoes = {}) {
        return requisitar("/api/onde-comprar/autocomplete", {
            ...opcoes,
            method: "POST",
            body: JSON.stringify({ texto, latitude, longitude, limite }),
        });
    },
    estabelecimentosProximos(latitude, longitude, raioKm = 15, opcoes = {}) {
        return requisitar("/api/onde-comprar/proximos", {
            ...opcoes, method: "POST", body: JSON.stringify({ latitude, longitude, raio_km: raioKm }),
        });
    },
    otimizarCompra(churrascoId, modo = "equilibrio", latitude = null, longitude = null, opcoes = {}) {
        return requisitar(`/api/onde-comprar/churrasco/${churrascoId}`, {
            ...opcoes, method: "POST", body: JSON.stringify({ modo, latitude, longitude }),
        });
    },
    registrarInteracoesEstabelecimentos(tipo, estabelecimentoIds, churrascoId = null, contexto = "onde_comprar", opcoes = {}) {
        return requisitar("/api/onde-comprar/interacoes", {
            ...opcoes, method: "POST", body: JSON.stringify({ tipo, estabelecimento_ids: estabelecimentoIds, churrasco_id: churrascoId, contexto }),
        });
    },

    listarPlanos(opcoes = {}) { return requisitar("/api/planos", opcoes); },
    minhaAssinatura(opcoes = {}) { return requisitar("/api/planos/minha-assinatura", opcoes); },

    documentosPrivacidade(opcoes = {}) { return requisitar("/api/privacidade/documentos", opcoes); },
    meusConsentimentos(opcoes = {}) { return requisitar("/api/privacidade/meus-consentimentos", opcoes); },
    atualizarMarketing(concedido, opcoes = {}) { return requisitar("/api/privacidade/marketing", { ...opcoes, method: "PUT", body: JSON.stringify({ concedido }) }); },
    exportarMeusDados(opcoes = {}) { return requisitar("/api/privacidade/exportar", opcoes); },
    excluirMinhaConta(senha, opcoes = {}) { return requisitar("/api/privacidade/minha-conta", { ...opcoes, method: "DELETE", body: JSON.stringify({ senha, confirmacao: "EXCLUIR" }) }); },

    adminDashboard(opcoes = {}) { return requisitar("/api/admin/dashboard", opcoes); },
    adminUsuarios(parametros = {}, opcoes = {}) { return requisitar(`/api/admin/usuarios${queryString(parametros)}`, opcoes); },
    adminAtualizarUsuario(id, payload, opcoes = {}) { return requisitar(`/api/admin/usuarios/${id}`, { ...opcoes, method: "PATCH", body: JSON.stringify(payload) }); },
    adminEstabelecimentos(parametros = {}, opcoes = {}) { return requisitar(`/api/admin/estabelecimentos${queryString(parametros)}`, opcoes); },
    adminAtualizarEstabelecimento(id, payload, opcoes = {}) { return requisitar(`/api/admin/estabelecimentos/${id}`, { ...opcoes, method: "PATCH", body: JSON.stringify(payload) }); },
    adminAuditoria(limite = 100, opcoes = {}) { return requisitar(`/api/admin/auditoria?limite=${encodeURIComponent(limite)}`, opcoes); },
};
