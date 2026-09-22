const CHAVE_ESTADO = "churrasplan_estado_v3";
const CHAVES_ESTADO_LEGADO = ["churrasplan_estado_v2", "churrasplan_estado"];

const _memoriaEstado = new Map();
let _usarMemoriaEstado = false;

function _lerStorage(chave) {
    if (_usarMemoriaEstado) return _memoriaEstado.has(chave) ? _memoriaEstado.get(chave) : null;
    try {
        const valor = window.localStorage.getItem(chave);
        if (valor !== null) _memoriaEstado.set(chave, valor);
        return valor;
    } catch {
        _usarMemoriaEstado = true;
        return _memoriaEstado.has(chave) ? _memoriaEstado.get(chave) : null;
    }
}

function _gravarStorage(chave, valor) {
    const serializado = String(valor);
    _memoriaEstado.set(chave, serializado);
    if (_usarMemoriaEstado) return;
    try { window.localStorage.setItem(chave, serializado); }
    catch { _usarMemoriaEstado = true; }
}

function _removerStorage(chave) {
    _memoriaEstado.delete(chave);
    if (_usarMemoriaEstado) return;
    try { window.localStorage.removeItem(chave); }
    catch { _usarMemoriaEstado = true; }
}

function gerarChavePlanejamento() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    return `plan-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function _numeroInteiroNaoNegativo(valor) {
    const numero = Number(valor);
    return Number.isFinite(numero) && numero >= 0 ? Math.floor(numero) : 0;
}

function _numeroPositivoOu(valor, fallback) {
    const numero = Number(valor);
    return Number.isFinite(numero) && numero > 0 ? numero : fallback;
}

function _numeroOpcionalNaoNegativo(valor) {
    if (valor === "" || valor === null || valor === undefined) return null;
    const numero = Number(valor);
    return Number.isFinite(numero) && numero >= 0 ? numero : null;
}

function _normalizarCarnes(carnes) {
    if (!Array.isArray(carnes)) return [];
    return carnes.map((item) => {
        if (!item || typeof item !== "object") return null;
        let slug = item.produto_slug || item.slug || null;
        let catalogo = null;
        if (typeof CATALOGO_CARNES !== "undefined") {
            catalogo = CATALOGO_CARNES.find((c) => c.slug === slug)
                || CATALOGO_CARNES.find((c) => c.nome.toLocaleLowerCase("pt-BR") === String(item.nome || "").toLocaleLowerCase("pt-BR"));
        }
        if (!slug && catalogo) slug = catalogo.slug;
        if (!slug) return null;
        const percentual = Number(item.percentual);
        return {
            nome: catalogo?.nome || item.nome || slug,
            produto_slug: slug,
            percentual: Number.isFinite(percentual) && percentual >= 0 ? percentual : 0,
        };
    }).filter(Boolean);
}

function _normalizarConvidados(origem = {}) {
    // Migração: v2 guardava homens/mulheres; v3 trabalha com adultos sem exigir sexo.
    const adultos = origem.adultos !== undefined
        ? _numeroInteiroNaoNegativo(origem.adultos)
        : _numeroInteiroNaoNegativo(origem.homens) + _numeroInteiroNaoNegativo(origem.mulheres);
    const criancas = _numeroInteiroNaoNegativo(origem.criancas);
    const adultosBebem = origem.adultos_bebem_alcool !== undefined
        ? _numeroInteiroNaoNegativo(origem.adultos_bebem_alcool)
        : _numeroInteiroNaoNegativo(origem.homens_bebem_alcool) + _numeroInteiroNaoNegativo(origem.mulheres_bebem_alcool);
    const total = adultos + criancas;
    const limitarTotal = (valor) => Math.min(_numeroInteiroNaoNegativo(valor), total);

    return {
        adultos,
        criancas,
        adultos_bebem_alcool: Math.min(adultosBebem, adultos),
        vegetarianos: limitarTotal(origem.vegetarianos),
        veganos: limitarTotal(origem.veganos),
        sem_carne_bovina: limitarTotal(origem.sem_carne_bovina),
        sem_carne_suina: limitarTotal(origem.sem_carne_suina),
        intolerantes_lactose: limitarTotal(origem.intolerantes_lactose),
        alergias: String(origem.alergias || "").slice(0, 2000),
        outras_restricoes: String(origem.outras_restricoes || "").slice(0, 2000),

        // Aliases legados mantêm previews/calculadoras antigas compatíveis.
        homens: adultos,
        mulheres: 0,
        homens_bebem_alcool: Math.min(adultosBebem, adultos),
        mulheres_bebem_alcool: 0,
    };
}

const EstadoChurrasco = {
    padrao() {
        return {
            planejamento_id: gerarChavePlanejamento(),
            etapa_atual: "planejamento",
            evento: { nome: "", data_evento: null, tipo: "", duracao_horas: 4 },
            convidados: _normalizarConvidados({}),
            orcamento_maximo: null,
            dividir_entre: null,
            perfil_consumo: "normal",
            perfil_personalizado: null,
            carnes: { selecionadas: [] },
            carvao_ativo: true,
            bebidas: { nao_alcoolicas_ativas: [], alcoolica_ativa: false, gelo_ativo: false },
            extras_ativos: [],
            acompanhamentos_ativos: [],
            churrasco_id: null,
            resultado_desatualizado: true,
        };
    },

    obter() {
        const padrao = this.padrao();
        let bruto = _lerStorage(CHAVE_ESTADO);
        let chaveLegada = null;
        if (!bruto) {
            for (const chave of CHAVES_ESTADO_LEGADO) {
                bruto = _lerStorage(chave);
                if (bruto) { chaveLegada = chave; break; }
            }
        }

        if (!bruto) {
            _gravarStorage(CHAVE_ESTADO, JSON.stringify(padrao));
            return padrao;
        }

        try {
            const salvo = JSON.parse(bruto);
            const convidados = _normalizarConvidados(salvo.convidados || {});
            const tipoEventoValido = typeof TIPOS_EVENTO === "undefined"
                || TIPOS_EVENTO.some((item) => item.chave === salvo.evento?.tipo);
            const perfilValido = typeof PERFIS_CONSUMO === "undefined"
                || PERFIS_CONSUMO.some((item) => item.chave === salvo.perfil_consumo);
            const duracaoSalva = _numeroPositivoOu(salvo.evento?.duracao_horas, padrao.evento.duracao_horas);
            const normalizado = {
                ...padrao,
                ...salvo,
                planejamento_id: salvo.planejamento_id || padrao.planejamento_id,
                etapa_atual: ["planejamento", "carnes", "bebidas", "extras", "resultado"].includes(salvo.etapa_atual)
                    ? salvo.etapa_atual : padrao.etapa_atual,
                evento: {
                    ...padrao.evento,
                    ...(salvo.evento || {}),
                    nome: String(salvo.evento?.nome || salvo.nome || "").slice(0, 150),
                    data_evento: salvo.evento?.data_evento || salvo.data_evento || null,
                    tipo: tipoEventoValido ? (salvo.evento?.tipo || "") : "",
                    duracao_horas: Math.min(48, Math.max(1, duracaoSalva)),
                },
                convidados,
                orcamento_maximo: _numeroOpcionalNaoNegativo(salvo.orcamento_maximo),
                dividir_entre: salvo.dividir_entre != null ? Math.max(2, _numeroInteiroNaoNegativo(salvo.dividir_entre)) : null,
                perfil_consumo: perfilValido ? salvo.perfil_consumo : padrao.perfil_consumo,
                carnes: { selecionadas: _normalizarCarnes(salvo.carnes?.selecionadas) },
                bebidas: {
                    ...padrao.bebidas,
                    ...(salvo.bebidas || {}),
                    nao_alcoolicas_ativas: Array.isArray(salvo.bebidas?.nao_alcoolicas_ativas)
                        ? salvo.bebidas.nao_alcoolicas_ativas : [],
                    alcoolica_ativa: Boolean(salvo.bebidas?.alcoolica_ativa),
                    gelo_ativo: Boolean(salvo.bebidas?.gelo_ativo),
                },
                extras_ativos: Array.isArray(salvo.extras_ativos) ? salvo.extras_ativos : [],
                acompanhamentos_ativos: Array.isArray(salvo.acompanhamentos_ativos) ? salvo.acompanhamentos_ativos : [],
            };

            if (convidados.adultos_bebem_alcool === 0) normalizado.bebidas.alcoolica_ativa = false;
            if (normalizado.dividir_entre && normalizado.dividir_entre > Math.max(2, convidados.adultos + convidados.criancas)) {
                normalizado.dividir_entre = Math.max(2, convidados.adultos + convidados.criancas);
            }

            _gravarStorage(CHAVE_ESTADO, JSON.stringify(normalizado));
            if (chaveLegada) _removerStorage(chaveLegada);
            return normalizado;
        } catch {
            _removerStorage(CHAVE_ESTADO);
            CHAVES_ESTADO_LEGADO.forEach(_removerStorage);
            _gravarStorage(CHAVE_ESTADO, JSON.stringify(padrao));
            return padrao;
        }
    },

    salvar(parcial, opcoes = {}) {
        const { invalidarResultado = true } = opcoes;
        const atual = this.obter();
        const convidadosMesclados = parcial.convidados
            ? _normalizarConvidados({ ...atual.convidados, ...parcial.convidados })
            : atual.convidados;
        const novo = {
            ...atual,
            ...parcial,
            evento: parcial.evento ? { ...atual.evento, ...parcial.evento } : atual.evento,
            convidados: convidadosMesclados,
            carnes: parcial.carnes ? { ...atual.carnes, ...parcial.carnes } : atual.carnes,
            bebidas: parcial.bebidas ? { ...atual.bebidas, ...parcial.bebidas } : atual.bebidas,
        };
        if (!Object.prototype.hasOwnProperty.call(parcial, "resultado_desatualizado") && invalidarResultado) {
            novo.resultado_desatualizado = true;
        }
        _gravarStorage(CHAVE_ESTADO, JSON.stringify(novo));
        return novo;
    },

    marcarEtapa(etapa) {
        return this.salvar({ etapa_atual: etapa }, { invalidarResultado: false });
    },

    limpar() {
        _removerStorage(CHAVE_ESTADO);
        CHAVES_ESTADO_LEGADO.forEach(_removerStorage);
        _memoriaEstado.clear();
    },

    totalPessoas() {
        const c = this.obter().convidados;
        return (c.adultos || 0) + (c.criancas || 0);
    },

    pessoasQueComemCarne() {
        const c = this.obter().convidados;
        const semCarne = Math.min((c.adultos || 0) + (c.criancas || 0), (c.vegetarianos || 0) + (c.veganos || 0));
        const adultosSemCarne = Math.min(c.adultos || 0, semCarne);
        const criancasSemCarne = Math.max(0, semCarne - adultosSemCarne);
        return {
            adultos: Math.max(0, (c.adultos || 0) - adultosSemCarne),
            criancas: Math.max(0, (c.criancas || 0) - criancasSemCarne),
        };
    },

    carregarResultadoSalvo(dados, { novaChave = false } = {}) {
        const itens = Array.isArray(dados.itens) ? dados.itens : [];
        const carnes = itens.filter((i) => i.categoria === "carne" && i.produto_slug).map((i) => ({
            nome: i.nome, produto_slug: i.produto_slug, percentual: Number(i.percentual || 0),
        }));
        const bebidas = itens.filter((i) => i.categoria === "bebida").map((i) => i.produto_slug).filter(Boolean);
        const extras = itens.filter((i) => i.categoria === "extra").map((i) => i.produto_slug).filter(Boolean);
        const acompanhamentos = itens.filter((i) => i.categoria === "acompanhamento").map((i) => i.produto_slug).filter(Boolean);
        const atual = this.padrao();
        const estado = {
            ...atual,
            planejamento_id: novaChave ? gerarChavePlanejamento() : (dados.chave_cliente || gerarChavePlanejamento()),
            etapa_atual: "resultado",
            evento: { nome: dados.nome || "", data_evento: dados.data_evento || null, tipo: dados.tipo_evento || "outro", duracao_horas: dados.duracao_horas || 4 },
            convidados: _normalizarConvidados({
                adultos: dados.adultos, criancas: dados.criancas, adultos_bebem_alcool: dados.adultos_bebem_alcool,
                vegetarianos: dados.vegetarianos, veganos: dados.veganos, sem_carne_bovina: dados.sem_carne_bovina,
                sem_carne_suina: dados.sem_carne_suina, intolerantes_lactose: dados.intolerantes_lactose,
                alergias: dados.alergias, outras_restricoes: dados.outras_restricoes,
            }),
            orcamento_maximo: dados.orcamento_maximo ?? null, dividir_entre: dados.dividir_entre ?? null,
            perfil_consumo: dados.perfil_consumo || "normal", perfil_personalizado: dados.perfil_personalizado || null,
            carnes: { selecionadas: carnes }, carvao_ativo: dados.carvao_ativo !== false,
            bebidas: { nao_alcoolicas_ativas: bebidas.filter((s) => !["cerveja", "gelo"].includes(s)), alcoolica_ativa: bebidas.includes("cerveja"), gelo_ativo: dados.gelo_ativo === true || bebidas.includes("gelo") },
            extras_ativos: extras.filter((s) => s !== "carvao"), acompanhamentos_ativos: acompanhamentos,
            churrasco_id: novaChave ? null : dados.id, resultado_desatualizado: novaChave,
        };
        _gravarStorage(CHAVE_ESTADO, JSON.stringify(estado));
        return estado;
    },
};
