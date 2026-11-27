const TEMPO_LIMITE_API_MS = 15000;
// No plano gratuito do Render, a API dorme depois de 15 minutos sem uso e leva
// cerca de um minuto para voltar. Nesse intervalo o proxy segura a requisição
// ou responde com erro. Ações como o login esperam a API responder em
// /api/health antes de enviar os dados.
const TEMPO_MAXIMO_ACORDAR_API_MS = 90000;
const TEMPO_TENTATIVA_SAUDE_MS = 20000;
const INTERVALO_TENTATIVAS_SAUDE_MS = 3000;
// O Render só desliga a API depois de 15 minutos sem tráfego, então uma
// resposta recente dispensa a checagem.
const API_ACORDADA_POR_MS = 5 * 60 * 1000;
let apiRespondeuEm = 0;
let esperaApiAcordar = null;
const CAMPOS_DATA_UTC = new Set(["criado_em", "atualizado_em", "ultimo_login_em", "email_verificado_em", "data_evento", "periodo_fim_em", "sincronizado_em", "expira_em", "verificado_em", "inicio_em", "fim_em", "tolerancia_ate", "quando"]);
function normalizarDatasServidor(valor, chave = "") {
    if (typeof valor === "string" && CAMPOS_DATA_UTC.has(chave) && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(valor)) return valor + "Z";
    if (Array.isArray(valor)) return valor.map(item => normalizarDatasServidor(item));
    if (valor && typeof valor === "object") return Object.fromEntries(Object.entries(valor).map(([k, v]) => [k, normalizarDatasServidor(v, k)]));
    return valor;
}

function lerCookie(nome) {
    const prefixo = `${encodeURIComponent(nome)}=`;
    const parte = document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith(prefixo));
    return parte ? decodeURIComponent(parte.slice(prefixo.length)) : null;
}

// Converte o "detail" da API em texto para a interface. O corpo completo
// continua disponível em erro.body para quem precisar do código do erro.
function mensagemErroApi(detalhe) {
    if (typeof detalhe === "string") return detalhe;
    if (Array.isArray(detalhe)) return "Alguns dados enviados não são válidos. Confira e tente novamente.";
    if (detalhe && typeof detalhe === "object") {
        if (typeof detalhe.mensagem === "string" && detalhe.mensagem) return detalhe.mensagem;
        if (detalhe.codigo === "LIMITE_MEMBROS_ATINGIDO") return "O limite de membros do plano foi atingido.";
        if (detalhe.codigo === "RECURSO_PLANO_NECESSARIO") return "Este recurso não está incluído no plano atual.";
    }
    return JSON.stringify(detalhe);
}

function erroSemConexaoApi(causa) {
    const rede = new Error("Não foi possível conectar à API do ChurrasPlan.");
    if (causa) rede.cause = causa;
    return rede;
}

async function sondarApi() {
    const limite = Date.now() + TEMPO_MAXIMO_ACORDAR_API_MS;
    while (Date.now() < limite) {
        if (navigator.onLine === false) throw erroSemConexaoApi();
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), Math.min(TEMPO_TENTATIVA_SAUDE_MS, Math.max(1000, limite - Date.now())));
        try {
            // O parâmetro evita que um cache no caminho responda pela API dormindo.
            const resposta = await fetch(`${API_BASE_URL}/api/health?t=${Date.now()}`, {
                headers: { Accept: "application/json" },
                cache: "no-store",
                credentials: "omit",
                signal: controller.signal,
            });
            // Enquanto acorda, o proxy pode devolver 502/503/504 ou uma página HTML.
            const corpo = await resposta.json().catch(() => null);
            if (resposta.ok && corpo?.status === "ok") {
                apiRespondeuEm = Date.now();
                return;
            }
        } catch (erro) {
            // Sem rede ou API inacessível (TypeError) falha na hora, como antes.
            // Um aborto aqui é só o tempo desta tentativa: tenta de novo.
            if (erro instanceof TypeError) throw erroSemConexaoApi(erro);
        } finally {
            window.clearTimeout(timer);
        }
        const restante = limite - Date.now();
        if (restante > 0) await new Promise((resolve) => window.setTimeout(resolve, Math.min(INTERVALO_TENTATIVAS_SAUDE_MS, restante)));
    }
    if (typeof ChurrasPlanTelemetria !== "undefined") ChurrasPlanTelemetria.registrar("timeout_api");
    const erro = new Error("O servidor do ChurrasPlan não respondeu. Tente novamente em alguns minutos.");
    erro.status = 503;
    throw erro;
}

/** Resolve quando a API está respondendo; espera até 90 s se ela estiver acordando. */
function aguardarApiDisponivel() {
    if (Date.now() - apiRespondeuEm < API_ACORDADA_POR_MS) return Promise.resolve();
    if (!esperaApiAcordar) esperaApiAcordar = sondarApi().finally(() => { esperaApiAcordar = null; });
    return esperaApiAcordar;
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
        // JSON abaixo de 500 vem da própria API (um 401 também conta). Erros do
        // proxy e a página de espera do Render não marcam a API como acordada.
        if (resposta.status < 500 && (corpo !== null || resposta.status === 204)) apiRespondeuEm = Date.now();

        if (!resposta.ok) {
            const detalhe = corpo && corpo.detail ? corpo.detail : `Erro ${resposta.status}`;
            if (detalhe?.codigo === "MFA_NECESSARIO" && window.location && !window.location.pathname.endsWith("seguranca.html")) {
                const next = window.location.pathname.split("/").pop() + window.location.search;
                window.location.assign("seguranca.html?next=" + encodeURIComponent(next));
            }
            const erro = new Error(mensagemErroApi(detalhe));
            erro.status = resposta.status;
            erro.body = corpo;
            throw erro;
        }
        return normalizarDatasServidor(corpo);
    } catch (erro) {
        if (typeof ChurrasPlanTelemetria !== "undefined" && (erro.status >= 500 || erro.name === "AbortError" || erro instanceof TypeError)) ChurrasPlanTelemetria.registrar(erro.name === "AbortError" ? "timeout_api" : "falha_api");
        if (erro.name === "AbortError") {
            const timeout = new Error("A API demorou demais para responder. Tente novamente.");
            timeout.status = 408;
            throw timeout;
        }
        if (erro instanceof TypeError) throw erroSemConexaoApi(erro);
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


/** Contexto de organização por aba; fallback em memória se storage estiver bloqueado. */
let organizacaoAtivaMemoria = null;
function definirOrganizacaoAtiva(id) {
    organizacaoAtivaMemoria = id ? String(id) : null;
}
function opcoesOrganizacao(opcoes = {}) {
    // O retorno autenticado do Checkout pode se referir a uma organização
    // diferente da selecionada na aba anterior. A escolha explícita prevalece;
    // o backend valida a titularidade, nunca confia no valor do navegador.
    if (opcoes.headers?.["X-Organizacao-ID"]) return opcoes;
    let id = organizacaoAtivaMemoria;
    if (!id) {
        try { id = sessionStorage.getItem("churrasplan_organizacao_id"); } catch { /* fallback */ }
    }
    if (!id || !/^[1-9][0-9]*$/.test(id)) return opcoes;
    return { ...opcoes, headers: { ...(opcoes.headers || {}), "X-Organizacao-ID": id } };
}

const ChurrasPlanAPI = {
    calcularCarnes(payload, opcoes = {}) { return requisitar("/api/calculadora/carnes", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    calcularBebidas(payload, opcoes = {}) { return requisitar("/api/calculadora/bebidas", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    calcularExtras(payload, opcoes = {}) { return requisitar("/api/calculadora/extras", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },

    criarChurrasco(payload, opcoes = {}) { return requisitar("/api/churrascos", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    obterChurrasco(id, opcoes = {}) { return requisitar(`/api/churrascos/${id}`, opcoes); },
    atualizarChurrasco(id, payload, opcoes = {}) { return requisitar(`/api/churrascos/${id}`, { ...opcoes, method: "PUT", body: JSON.stringify(payload) }); },
    meusChurrascos(opcoes = {}) { return requisitar("/api/churrascos/meus", opcoes); },
    meusBeneficios(opcoes = {}) { return requisitar("/api/planos/meus-beneficios", opcoes); },
    analiseCustosPremium(id, opcoes = {}) { return requisitar(`/api/churrascos/${id}/analise-custos`, opcoes); },
    comparacaoAvancadaPremium(id, opcoes = {}) {
        return requisitar(`/api/onde-comprar/churrasco/${id}/comparacao-avancada`, {
            ...opcoes, method: "POST", body: JSON.stringify({ modo: "equilibrio" }),
        });
    },
    listarModelosEvento(opcoes = {}) { return requisitar("/api/modelos-evento", opcoes); },
    criarModeloEvento(id, nome, opcoes = {}) {
        return requisitar("/api/modelos-evento", {
            ...opcoes, method: "POST", body: JSON.stringify({ churrasco_id: id, nome }),
        });
    },
    usarModeloEvento(id, opcoes = {}) {
        return requisitar(`/api/modelos-evento/${id}/usar`, {
            ...opcoes, method: "POST", body: JSON.stringify({}),
        });
    },
    excluirModeloEvento(id, opcoes = {}) {
        return requisitar(`/api/modelos-evento/${id}`, { ...opcoes, method: "DELETE" });
    },
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
    listarGenericos(opcoes = {}) { return requisitar("/api/produtos/genericos", opcoes); },

    definirOrganizacaoAtiva,
    ativarParceiro(opcoes = {}) { return requisitar("/api/parceiro/ativar", { ...opcoes, method: "POST" }); },
    organizacoesParceiro(opcoes = {}) { return requisitar("/api/parceiro/organizacoes", opcoes); },
    entitlementsParceiro(opcoes = {}) { return requisitar("/api/parceiro/entitlements", opcoesOrganizacao(opcoes)); },
    membrosOrganizacao(opcoes = {}) { return requisitar("/api/parceiro/equipe/membros", opcoesOrganizacao(opcoes)); },
    convitesOrganizacao(opcoes = {}) { return requisitar("/api/parceiro/equipe/convites", opcoesOrganizacao(opcoes)); },
    enviarConviteOrganizacao(payload, opcoes = {}) { return requisitar("/api/parceiro/equipe/convites", { ...opcoesOrganizacao(opcoes), method: "POST", body: JSON.stringify(payload) }); },
    revogarConviteOrganizacao(id, opcoes = {}) { return requisitar(`/api/parceiro/equipe/convites/${id}`, { ...opcoesOrganizacao(opcoes), method: "DELETE" }); },
    aceitarConviteOrganizacao(token, opcoes = {}) { return requisitar("/api/parceiro/convites/aceitar", { ...opcoes, method: "POST", body: JSON.stringify({ token }) }); },
    alterarPapelMembro(id, papel, opcoes = {}) { return requisitar(`/api/parceiro/equipe/membros/${id}`, { ...opcoesOrganizacao(opcoes), method: "PATCH", body: JSON.stringify({ papel }) }); },
    removerMembroOrganizacao(id, opcoes = {}) { return requisitar(`/api/parceiro/equipe/membros/${id}`, { ...opcoesOrganizacao(opcoes), method: "DELETE" }); },
    dashboardParceiro(opcoes = {}) { return requisitar("/api/parceiro/dashboard", opcoesOrganizacao(opcoes)); },
    estabelecimentosParceiro(opcoes = {}) { return requisitar("/api/parceiro/estabelecimentos", opcoesOrganizacao(opcoes)); },
    criarEstabelecimento(payload, opcoes = {}) { return requisitar("/api/parceiro/estabelecimentos", { ...opcoesOrganizacao(opcoes), method: "POST", body: JSON.stringify(payload) }); },
    produtosParceiro(opcoes = {}) { return requisitar("/api/parceiro/produtos", opcoesOrganizacao(opcoes)); },
    criarProdutoComercial(payload, opcoes = {}) { return requisitar("/api/parceiro/produtos", { ...opcoesOrganizacao(opcoes), method: "POST", body: JSON.stringify(payload) }); },
    cadastrarPrecoParceiro(payload, opcoes = {}) { return requisitar("/api/parceiro/precos", { ...opcoesOrganizacao(opcoes), method: "POST", body: JSON.stringify(payload) }); },
    filiaisParceiro(opcoes = {}) { return requisitar("/api/parceiro/filiais", opcoesOrganizacao(opcoes)); },
    alterarFilial(id, payload, opcoes = {}) { return requisitar(`/api/parceiro/filiais/${id}`, { ...opcoesOrganizacao(opcoes), method: "PATCH", body: JSON.stringify(payload) }); },
    onboardingParceiro(opcoes = {}) { return requisitar("/api/parceiro/onboarding", opcoesOrganizacao(opcoes)); },
    relatorioComercialParceiro(dias = 30, opcoes = {}) { return requisitar(`/api/parceiro/relatorios/comercial?periodo_dias=${Number(dias)}`, opcoesOrganizacao(opcoes)); },
    importarOfertasCSV(payload, opcoes = {}) { return requisitar("/api/parceiro/importacoes/ofertas", { ...opcoesOrganizacao(opcoes), method: "POST", body: JSON.stringify(payload) }); },
    importarCatalogoCSV(payload, opcoes = {}) { return requisitar("/api/parceiro/importacoes/catalogo", { ...opcoesOrganizacao(opcoes), method: "POST", body: JSON.stringify(payload) }); },
    billingUsuarioCatalogo(opcoes = {}) { return requisitar("/api/billing/usuario/catalogo", opcoes); },
    billingUsuarioAssinatura(opcoes = {}) { return requisitar("/api/billing/usuario/assinatura", opcoes); },
    billingUsuarioCheckout(payload, opcoes = {}) { return requisitar("/api/billing/usuario/checkout", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    billingUsuarioSincronizar(opcoes = {}) { return requisitar("/api/billing/usuario/sincronizar", { ...opcoes, method: "POST" }); },
    billingUsuarioPortal(opcoes = {}) { return requisitar("/api/billing/usuario/portal", { ...opcoes, method: "POST" }); },
    billingUsuarioFaturas(opcoes = {}) { return requisitar("/api/billing/usuario/faturas", opcoes); },
    billingUsuarioCancelar(opcoes = {}) { return requisitar("/api/billing/usuario/cancelar", { ...opcoes, method: "POST" }); },
    billingUsuarioReativar(opcoes = {}) { return requisitar("/api/billing/usuario/reativar", { ...opcoes, method: "POST" }); },
    billingUsuarioTrocarPeriodo(payload, opcoes = {}) { return requisitar("/api/billing/usuario/trocar-periodo", { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    billingPlanosPublicos(opcoes = {}) { return requisitar("/api/billing/planos-publicos", opcoes); },
    billingAssinatura(opcoes = {}) { return requisitar("/api/billing/assinatura", opcoesOrganizacao(opcoes)); },
    billingCatalogo(opcoes = {}) { return requisitar("/api/billing/catalogo", opcoesOrganizacao(opcoes)); },
    billingFaturas(opcoes = {}) { return requisitar("/api/billing/faturas", opcoesOrganizacao(opcoes)); },
    billingCheckout(payload, opcoes = {}) { return requisitar("/api/billing/checkout", { ...opcoesOrganizacao(opcoes), method: "POST", body: JSON.stringify(payload) }); },
    billingTrocarPlano(payload, opcoes = {}) { return requisitar("/api/billing/trocar-plano", { ...opcoesOrganizacao(opcoes), method: "POST", body: JSON.stringify(payload) }); },
    billingCancelar(opcoes = {}) { return requisitar("/api/billing/cancelar", { ...opcoesOrganizacao(opcoes), method: "POST" }); },
    billingReativar(opcoes = {}) { return requisitar("/api/billing/reativar", { ...opcoesOrganizacao(opcoes), method: "POST" }); },
    billingSincronizar(opcoes = {}) { return requisitar("/api/billing/sincronizar", { ...opcoesOrganizacao(opcoes), method: "POST" }); },
    billingPortal(opcoes = {}) { return requisitar("/api/billing/portal", { ...opcoesOrganizacao(opcoes), method: "POST" }); },
    ofertasCampanhaParceiro(opcoes = {}) { return requisitar("/api/parceiro/ofertas/campanhas", opcoesOrganizacao(opcoes)); },
    campanhasParceiro(opcoes = {}) { return requisitar("/api/parceiro/campanhas", opcoesOrganizacao(opcoes)); },
    criarCampanhaParceiro(payload, opcoes = {}) { return requisitar("/api/parceiro/campanhas", { ...opcoesOrganizacao(opcoes), method: "POST", body: JSON.stringify(payload) }); },
    atualizarCampanhaParceiro(id, payload, opcoes = {}) { return requisitar(`/api/parceiro/campanhas/${id}`, { ...opcoesOrganizacao(opcoes), method: "PUT", body: JSON.stringify(payload) }); },
    enviarCampanhaParceiro(id, opcoes = {}) { return requisitar(`/api/parceiro/campanhas/${id}/enviar`, { ...opcoesOrganizacao(opcoes), method: "POST" }); },
    cancelarCampanhaParceiro(id, opcoes = {}) { return requisitar(`/api/parceiro/campanhas/${id}/cancelar`, { ...opcoesOrganizacao(opcoes), method: "POST" }); },
    adminCampanhasPendentes(opcoes = {}) { return requisitar("/api/admin/campanhas/pendentes", opcoes); },
    adminRevisarCampanha(id, payload, opcoes = {}) { return requisitar(`/api/admin/campanhas/${id}/revisar`, { ...opcoes, method: "POST", body: JSON.stringify(payload) }); },
    campanhasPublicas(opcoes = {}) { return requisitar("/api/campanhas/ativas", opcoes); },

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
