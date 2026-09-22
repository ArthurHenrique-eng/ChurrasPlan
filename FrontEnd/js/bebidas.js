let estadoAtual = EstadoChurrasco.obter();
let sequenciaPreview = 0;
let timerPreview = null;

function renderizarBebidasNaoAlcoolicas() {
    const container = document.getElementById("lista-bebidas-na");
    const ativas = new Set(estadoAtual.bebidas.nao_alcoolicas_ativas || []);
    container.innerHTML = CATALOGO_BEBIDAS_NAO_ALCOOLICAS.map((bebida) => `
        <div class="item-config">
            <input type="checkbox" data-bebida="${bebida.chave}" ${ativas.has(bebida.chave) ? "checked" : ""}>
            <span class="item-config__nome">${escaparHTML(bebida.nome)}</span>
        </div>`).join("");
}

function coletarBebidasNaoAlcoolicasAtivas() {
    return [...document.querySelectorAll("#lista-bebidas-na input[data-bebida]:checked")].map((i) => i.dataset.bebida);
}

function nomeBebida(chave) {
    return CATALOGO_BEBIDAS_NAO_ALCOOLICAS.find((b) => b.chave === chave)?.nome || chave;
}

function textoCompra(compra) {
    if (!compra) return "";
    if (compra.quantidade_embalagens != null) {
        return `${formatarNumero(compra.compra)} ${escaparHTML(compra.unidade_compra)} (${compra.quantidade_embalagens} ${escaparHTML(compra.unidade_venda)}(s))`;
    }
    return `${formatarNumero(compra.compra)} ${escaparHTML(compra.unidade_compra)}`;
}

function coletarEstadoBebidas() {
    const campoAlcool = document.getElementById("campo-alcool-ativo");
    const campoGelo = document.getElementById("campo-gelo-ativo");
    return {
        nao_alcoolicas_ativas: coletarBebidasNaoAlcoolicasAtivas(),
        alcoolica_ativa: !campoAlcool.disabled && campoAlcool.checked,
        gelo_ativo: campoGelo.checked,
    };
}

function salvarRascunhoBebidas(etapa = "bebidas") {
    estadoAtual = EstadoChurrasco.salvar({ etapa_atual: etapa, bebidas: coletarEstadoBebidas() });
}

function agendarPreview() {
    // Invalida imediatamente qualquer resposta em voo; o novo request pode
    // esperar o debounce sem permitir que dados antigos reapareçam na tela.
    sequenciaPreview += 1;
    window.clearTimeout(timerPreview);
    timerPreview = window.setTimeout(atualizarPreview, 140);
}

async function atualizarPreview() {
    window.clearTimeout(timerPreview);
    const minhaSequencia = ++sequenciaPreview;
    const previewEl = document.getElementById("preview-bebidas");
    const bebidasAtivas = coletarBebidasNaoAlcoolicasAtivas();
    const alcoolAtiva = !document.getElementById("campo-alcool-ativo").disabled && document.getElementById("campo-alcool-ativo").checked;
    const geloAtivo = document.getElementById("campo-gelo-ativo").checked;

    if (!bebidasAtivas.length && !alcoolAtiva && !geloAtivo) {
        previewEl.style.display = "none";
        return;
    }

    try {
        const resultado = await ChurrasPlanAPI.calcularBebidas({
            homens: estadoAtual.convidados.adultos,
            mulheres: 0,
            criancas: estadoAtual.convidados.criancas,
            homens_bebem_alcool: estadoAtual.convidados.adultos_bebem_alcool,
            mulheres_bebem_alcool: 0,
            duracao_horas: estadoAtual.evento.duracao_horas,
            tipo_evento: estadoAtual.evento.tipo || "outro",
            perfil_consumo: estadoAtual.perfil_consumo,
            perfil_personalizado: estadoAtual.perfil_consumo === "personalizado" ? estadoAtual.perfil_personalizado : null,
            bebidas_nao_alcoolicas_ativas: bebidasAtivas,
            bebida_alcoolica_ativa: alcoolAtiva,
            gelo_ativo: geloAtivo,
        });
        if (minhaSequencia !== sequenciaPreview) return;

        previewEl.style.display = "block";
        const linhas = Object.entries(resultado.nao_alcoolicas_litros).map(([chave, litros]) => {
            const compra = resultado.nao_alcoolicas_compra[chave];
            return `<div class="hero__aside-linha"><span>${escaparHTML(nomeBebida(chave))}</span><strong>${formatarNumero(litros)} L necessários → ${textoCompra(compra)}</strong></div>`;
        }).join("");
        const linhaAlcool = alcoolAtiva
            ? `<div class="hero__aside-linha"><span>Cerveja</span><strong>${formatarNumero(resultado.alcool_litros_total)} L necessários → ${resultado.alcool_unidades_sugeridas} ${escaparHTML(resultado.alcool_unidade_venda)}(s)</strong></div>`
            : "";
        const linhaGelo = geloAtivo
            ? `<div class="hero__aside-linha"><span>Gelo</span><strong>${formatarNumero(resultado.gelo_kg)} kg necessários → ${formatarNumero(resultado.gelo_compra_kg)} kg (${resultado.gelo_sacos} saco(s))</strong></div>`
            : "";
        document.getElementById("preview-bebidas-conteudo").innerHTML = linhas + linhaAlcool + linhaGelo;
    } catch {
        if (minhaSequencia === sequenciaPreview) previewEl.style.display = "none";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (EstadoChurrasco.totalPessoas() === 0) { irPara("planejamento.html"); return; }
    if (!estadoAtual.carnes.selecionadas.length) { irPara("carnes.html"); return; }

    estadoAtual = EstadoChurrasco.marcarEtapa("bebidas");
    renderizarStepper(document.getElementById("stepper"), "bebidas");
    renderizarBebidasNaoAlcoolicas();

    const totalQueBebem = estadoAtual.convidados.adultos_bebem_alcool || 0;
    document.getElementById("resumo-quem-bebe").textContent = totalQueBebem > 0
        ? `${totalQueBebem} adulto(s) marcados como consumidores de bebida alcoólica.`
        : "Nenhum adulto foi marcado como consumidor de álcool.";

    const campoAlcool = document.getElementById("campo-alcool-ativo");
    const campoGelo = document.getElementById("campo-gelo-ativo");
    campoAlcool.disabled = totalQueBebem === 0;
    campoAlcool.checked = totalQueBebem > 0 && Boolean(estadoAtual.bebidas.alcoolica_ativa);
    campoGelo.checked = Boolean(estadoAtual.bebidas.gelo_ativo);

    if (totalQueBebem === 0 && estadoAtual.bebidas.alcoolica_ativa) salvarRascunhoBebidas();

    const aoAlterar = () => {
        salvarRascunhoBebidas();
        agendarPreview();
    };
    document.getElementById("lista-bebidas-na").addEventListener("change", aoAlterar);
    campoAlcool.addEventListener("change", aoAlterar);
    campoGelo.addEventListener("change", aoAlterar);
    atualizarPreview();

    document.getElementById("form-bebidas").addEventListener("submit", (evento) => {
        evento.preventDefault();
        salvarRascunhoBebidas("extras");
        irPara("extras.html");
    });
});
