/**
 * extras.js
 * Etapa 4: produtos extras e acompanhamentos. O rascunho é salvo enquanto
 * o usuário marca/desmarca itens e as respostas antigas de preview são
 * descartadas quando uma nova interação ocorre.
 */

let estadoAtual = EstadoChurrasco.obter();
let sequenciaPreview = 0;
let timerPreview = null;

function renderizarLista(container, catalogo, ativos) {
    const setAtivos = new Set(ativos || []);
    container.innerHTML = catalogo.map((item) => `
        <div class="item-config">
            <input type="checkbox" data-item="${item.chave}" ${setAtivos.has(item.chave) ? "checked" : ""}>
            <span class="item-config__nome">${escaparHTML(item.nome)}</span>
        </div>
    `).join("");
}

function coletarAtivos(container) {
    return [...container.querySelectorAll("input[data-item]:checked")].map((input) => input.dataset.item);
}

function salvarRascunhoExtras(etapa = "extras") {
    estadoAtual = EstadoChurrasco.salvar({
        etapa_atual: etapa,
        extras_ativos: coletarAtivos(document.getElementById("lista-extras")),
        acompanhamentos_ativos: coletarAtivos(document.getElementById("lista-acompanhamentos")),
    });
}

function agendarPreview() {
    // Invalida imediatamente qualquer resposta em voo; o novo request pode
    // esperar o debounce sem permitir que dados antigos reapareçam na tela.
    sequenciaPreview += 1;
    window.clearTimeout(timerPreview);
    timerPreview = window.setTimeout(atualizarPreview, 140);
}

function descricaoPreviewExtra(chave) {
    const normalizada = chave.replace(/_kg|_litros|_unidades|_rolos/g, "");
    const chaveCatalogo = normalizada
        .replace(/^sal_grosso$/, "sal_grosso")
        .replace(/^fosforo_isqueiro$/, "fosforo_isqueiro");
    return CATALOGO_EXTRAS.find((i) => i.chave === chaveCatalogo)?.nome
        || CATALOGO_ACOMPANHAMENTOS.find((i) => i.chave === chaveCatalogo)?.nome
        || normalizada.replace(/_/g, " ").replace(/^./, (c) => c.toLocaleUpperCase("pt-BR"));
}

function unidadePreviewExtra(chave) {
    if (chave.endsWith("_kg")) return "kg";
    if (chave.endsWith("_litros")) return "L";
    if (chave.endsWith("_rolos")) return "rolo(s)";
    return "un.";
}

async function atualizarPreview() {
    window.clearTimeout(timerPreview);
    const minhaSequencia = ++sequenciaPreview;
    const previewEl = document.getElementById("preview-extras");
    const extrasAtivos = coletarAtivos(document.getElementById("lista-extras"));
    const acompanhamentosAtivos = coletarAtivos(document.getElementById("lista-acompanhamentos"));

    if (extrasAtivos.length === 0 && acompanhamentosAtivos.length === 0) {
        previewEl.style.display = "none";
        return;
    }

    try {
        const pessoasCarne = EstadoChurrasco.pessoasQueComemCarne();
        const respostaCarnes = await ChurrasPlanAPI.calcularCarnes({
            homens: pessoasCarne.adultos,
            mulheres: 0,
            criancas: pessoasCarne.criancas,
            duracao_horas: estadoAtual.evento.duracao_horas,
            tipo_evento: estadoAtual.evento.tipo || "outro",
            perfil_consumo: estadoAtual.perfil_consumo,
            perfil_personalizado: estadoAtual.perfil_consumo === "personalizado" ? estadoAtual.perfil_personalizado : null,
            carnes: estadoAtual.carnes.selecionadas,
            carvao_ativo: estadoAtual.carvao_ativo !== false,
        });
        if (minhaSequencia !== sequenciaPreview) return;

        const resultado = await ChurrasPlanAPI.calcularExtras({
            pessoas_total: EstadoChurrasco.totalPessoas(),
            carne_total_kg: respostaCarnes.total_kg,
            extras_ativos: extrasAtivos,
            acompanhamentos_ativos: acompanhamentosAtivos,
        });
        if (minhaSequencia !== sequenciaPreview) return;

        previewEl.style.display = "block";
        const todasLinhas = { ...resultado.extras, ...resultado.acompanhamentos };
        document.getElementById("preview-extras-conteudo").innerHTML = Object.entries(todasLinhas)
            .map(([nome, valor]) => `<div class="hero__aside-linha"><span>${escaparHTML(descricaoPreviewExtra(nome))}</span><strong>${formatarNumero(valor)} ${unidadePreviewExtra(nome)}</strong></div>`)
            .join("");
    } catch {
        if (minhaSequencia === sequenciaPreview) previewEl.style.display = "none";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (EstadoChurrasco.totalPessoas() === 0) { irPara("planejamento.html"); return; }
    if (!estadoAtual.carnes.selecionadas.length) { irPara("carnes.html"); return; }

    estadoAtual = EstadoChurrasco.marcarEtapa("extras");
    renderizarStepper(document.getElementById("stepper"), "extras");
    renderizarLista(document.getElementById("lista-extras"), CATALOGO_EXTRAS, estadoAtual.extras_ativos);
    renderizarLista(document.getElementById("lista-acompanhamentos"), CATALOGO_ACOMPANHAMENTOS, estadoAtual.acompanhamentos_ativos);

    const aoAlterar = () => {
        salvarRascunhoExtras();
        agendarPreview();
    };
    document.getElementById("lista-extras").addEventListener("change", aoAlterar);
    document.getElementById("lista-acompanhamentos").addEventListener("change", aoAlterar);
    atualizarPreview();

    document.getElementById("form-extras").addEventListener("submit", (evento) => {
        evento.preventDefault();
        salvarRascunhoExtras("resultado");
        irPara("resultado.html");
    });
});
