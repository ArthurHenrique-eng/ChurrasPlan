let estadoAtual = EstadoChurrasco.obter();
let sequenciaPreview = 0;
let timerPreview = null;

function chaveCarneEstado(carneSalva) {
    if (carneSalva.produto_slug) return carneSalva.produto_slug;
    const catalogo = CATALOGO_CARNES.find((c) => c.nome.toLocaleLowerCase("pt-BR") === String(carneSalva.nome || "").toLocaleLowerCase("pt-BR"));
    return catalogo?.slug || carneSalva.nome;
}

let selecionadas = new Map((estadoAtual.carnes.selecionadas || []).map((c) => [chaveCarneEstado(c), {
    ...c,
    produto_slug: chaveCarneEstado(c),
}]));

function salvarRascunhoCarnes(etapa = "carnes") {
    estadoAtual = EstadoChurrasco.salvar({
        etapa_atual: etapa,
        carnes: { selecionadas: [...selecionadas.values()] },
        carvao_ativo: document.getElementById("campo-carvao-ativo").checked,
    });
}

function agendarPreview() {
    // Invalida imediatamente qualquer resposta em voo; o novo request pode
    // esperar o debounce sem permitir que dados antigos reapareçam na tela.
    sequenciaPreview += 1;
    window.clearTimeout(timerPreview);
    timerPreview = window.setTimeout(atualizarPreview, 160);
}

function renderizarListaCarnes() {
    const container = document.getElementById("lista-carnes");
    container.innerHTML = CATALOGO_CARNES.map((carne) => {
        const item = selecionadas.get(carne.slug);
        const marcado = Boolean(item);
        const percentual = marcado ? item.percentual : "";
        return `
            <div class="item-config item-carne">
                <input type="checkbox" data-carne="${carne.slug}" ${marcado ? "checked" : ""}>
                <span class="item-config__nome">${escaparHTML(carne.nome)}</span>
                <div class="campo-percentual" style="${marcado ? "" : "visibility:hidden"}">
                    <input type="number" min="0" max="100" step="1" data-percentual="${carne.slug}" value="${percentual}">
                    <span>%</span>
                </div>
            </div>`;
    }).join("");

    container.querySelectorAll("input[data-carne]").forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            const carne = CATALOGO_CARNES.find((c) => c.slug === checkbox.dataset.carne);
            const campo = checkbox.closest(".item-carne").querySelector(".campo-percentual");
            if (checkbox.checked) {
                selecionadas.set(carne.slug, { nome: carne.nome, produto_slug: carne.slug, percentual: 0 });
                campo.style.visibility = "visible";
            } else {
                selecionadas.delete(carne.slug);
                campo.style.visibility = "hidden";
            }
            atualizarResumoPercentual();
            salvarRascunhoCarnes();
            agendarPreview();
        });
    });

    container.querySelectorAll("input[data-percentual]").forEach((input) => {
        input.addEventListener("input", () => {
            const item = selecionadas.get(input.dataset.percentual);
            if (item) item.percentual = Number(input.value) || 0;
            atualizarResumoPercentual();
            salvarRascunhoCarnes();
            agendarPreview();
        });
    });
}

function atualizarResumoPercentual() {
    const soma = [...selecionadas.values()].reduce((t, item) => t + Number(item.percentual || 0), 0);
    const valorEl = document.getElementById("soma-percentual");
    const barraEl = document.getElementById("barra-percentual-preenchimento");
    const botaoEl = document.getElementById("botao-avancar");
    const somaArredondada = Math.round(soma * 100) / 100;
    valorEl.textContent = `${somaArredondada}%`;
    valorEl.classList.toggle("ok", Math.abs(soma - 100) < 0.01);
    barraEl.style.width = `${Math.max(0, Math.min(soma, 100))}%`;
    barraEl.style.background = Math.abs(soma - 100) < 0.01 ? "var(--sucesso)" : "var(--fogo)";
    const valido = Math.abs(soma - 100) < 0.01 && selecionadas.size > 0;
    botaoEl.disabled = !valido;
    return valido;
}

function distribuirIgualmente() {
    const itens = [...selecionadas.values()];
    if (!itens.length) return;
    const parte = Math.floor(100 / itens.length);
    const resto = 100 - parte * itens.length;
    itens.forEach((item, i) => { item.percentual = parte + (i === 0 ? resto : 0); });
    renderizarListaCarnes();
    atualizarResumoPercentual();
    salvarRascunhoCarnes();
    atualizarPreview();
}

async function atualizarPreview() {
    window.clearTimeout(timerPreview);
    const minhaSequencia = ++sequenciaPreview;
    const previewEl = document.getElementById("preview-total");
    if (selecionadas.size === 0 || !atualizarResumoPercentual()) {
        previewEl.style.display = "none";
        return;
    }

    try {
        const carvaoAtivo = document.getElementById("campo-carvao-ativo").checked;
        const pessoasCarne = EstadoChurrasco.pessoasQueComemCarne();
        const resultado = await ChurrasPlanAPI.calcularCarnes({
            homens: pessoasCarne.adultos,
            mulheres: 0,
            criancas: pessoasCarne.criancas,
            duracao_horas: estadoAtual.evento.duracao_horas,
            tipo_evento: estadoAtual.evento.tipo || "outro",
            perfil_consumo: estadoAtual.perfil_consumo,
            perfil_personalizado: estadoAtual.perfil_consumo === "personalizado" ? estadoAtual.perfil_personalizado : null,
            carnes: [...selecionadas.values()],
            carvao_ativo: carvaoAtivo,
        });
        if (minhaSequencia !== sequenciaPreview) return;
        previewEl.style.display = "flex";
        document.getElementById("preview-total-kg").textContent = `${formatarNumero(resultado.total_kg)} kg`;
        document.getElementById("preview-carvao-kg").textContent = carvaoAtivo
            ? `${formatarNumero(resultado.carvao_necessario_kg)} kg necessários → ${formatarNumero(resultado.carvao_compra_kg)} kg para compra (${resultado.carvao_sacos} saco(s))`
            : "não incluído";
    } catch {
        if (minhaSequencia === sequenciaPreview) previewEl.style.display = "none";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (EstadoChurrasco.totalPessoas() === 0) { irPara("planejamento.html"); return; }
    estadoAtual = EstadoChurrasco.marcarEtapa("carnes");
    renderizarStepper(document.getElementById("stepper"), "carnes");
    renderizarListaCarnes();
    atualizarResumoPercentual();
    document.getElementById("campo-carvao-ativo").checked = estadoAtual.carvao_ativo !== false;

    document.getElementById("campo-carvao-ativo").addEventListener("change", () => {
        salvarRascunhoCarnes();
        atualizarPreview();
    });
    document.getElementById("botao-distribuir").addEventListener("click", distribuirIgualmente);
    atualizarPreview();

    document.getElementById("form-carnes").addEventListener("submit", (evento) => {
        evento.preventDefault();
        if (!atualizarResumoPercentual()) return;
        salvarRascunhoCarnes("bebidas");
        irPara("bebidas.html");
    });
});
