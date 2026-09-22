/** Etapa 1: encontro, convidados, orçamento e perfil. */
let estadoAtual = EstadoChurrasco.obter();
let timerRascunho = null;

function renderizarOpcoesEvento() {
    const container = document.getElementById("opcoes-evento");
    container.innerHTML = TIPOS_EVENTO.map((tipo) => `
        <label class="opcao-cartao ${estadoAtual.evento.tipo === tipo.chave ? "selecionada" : ""}" data-evento="${tipo.chave}">
            <input type="radio" name="tipo-evento" value="${tipo.chave}" ${estadoAtual.evento.tipo === tipo.chave ? "checked" : ""}>
            <div class="opcao-cartao__titulo">${tipo.nome}</div>
            <p class="opcao-cartao__descricao">${tipo.descricao}</p>
        </label>`).join("");
    container.querySelectorAll(".opcao-cartao").forEach((el) => el.addEventListener("click", () => {
        container.querySelectorAll(".opcao-cartao").forEach((e) => e.classList.remove("selecionada"));
        el.classList.add("selecionada");
        estadoAtual.evento.tipo = el.dataset.evento;
        agendarSalvamentoRascunho();
    }));
}

function renderizarOpcoesPerfil() {
    const container = document.getElementById("opcoes-perfil");
    container.innerHTML = PERFIS_CONSUMO.map((perfil) => `
        <label class="opcao-cartao ${estadoAtual.perfil_consumo === perfil.chave ? "selecionada" : ""}" data-perfil="${perfil.chave}">
            <input type="radio" name="perfil-consumo" value="${perfil.chave}" ${estadoAtual.perfil_consumo === perfil.chave ? "checked" : ""}>
            <div class="opcao-cartao__titulo">${perfil.nome}</div>
            <p class="opcao-cartao__descricao">${perfil.descricao}</p>
        </label>`).join("");
    container.querySelectorAll(".opcao-cartao").forEach((el) => el.addEventListener("click", () => {
        container.querySelectorAll(".opcao-cartao").forEach((e) => e.classList.remove("selecionada"));
        el.classList.add("selecionada");
        estadoAtual.perfil_consumo = el.dataset.perfil;
        atualizarVisibilidadePersonalizado();
        agendarSalvamentoRascunho();
    }));
    atualizarVisibilidadePersonalizado();
}

function atualizarVisibilidadePersonalizado() {
    document.getElementById("bloco-personalizado").style.display = estadoAtual.perfil_consumo === "personalizado" ? "block" : "none";
}

const CAMPOS_PERSONALIZADOS = {
    "perso-carne-adulto": "carne_adulto_kg", "perso-carne-crianca": "carne_crianca_kg",
    "perso-agua": "agua_litros_pessoa", "perso-refrigerante": "refrigerante_litros_pessoa",
    "perso-suco": "suco_litros_pessoa", "perso-cerveja": "cerveja_litros_consumidor_hora",
    "perso-gelo": "gelo_kg_pessoa", "perso-carvao": "carvao_kg_por_kg_carne",
};
const CAMPOS_RESTRICOES_NUMERICAS = ["campo-vegetarianos", "campo-veganos", "campo-sem-bovina", "campo-sem-suina", "campo-lactose"];

function preencherCamposPersonalizado() {
    const p = estadoAtual.perfil_personalizado || {};
    Object.entries(CAMPOS_PERSONALIZADOS).forEach(([id, chave]) => {
        if (p[chave] !== undefined) document.getElementById(id).value = p[chave];
    });
}

function coletarPerfilPersonalizado() {
    const resultado = {};
    Object.entries(CAMPOS_PERSONALIZADOS).forEach(([id, chave]) => {
        const valor = document.getElementById(id).value;
        if (valor !== "" && valor !== null) resultado[chave] = Number(valor);
    });
    return resultado;
}

function paraDatetimeLocal(valor) {
    if (!valor) return "";
    const data = new Date(valor);
    if (Number.isNaN(data.getTime())) return "";
    const local = new Date(data.getTime() - data.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
}

function preencherCampos() {
    const c = estadoAtual.convidados;
    document.getElementById("campo-nome").value = estadoAtual.evento.nome || "";
    document.getElementById("campo-data-evento").value = paraDatetimeLocal(estadoAtual.evento.data_evento);
    document.getElementById("campo-duracao").value = estadoAtual.evento.duracao_horas || 4;
    document.getElementById("campo-orcamento").value = estadoAtual.orcamento_maximo ?? "";
    document.getElementById("campo-adultos").value = c.adultos || 0;
    document.getElementById("campo-criancas").value = c.criancas || 0;
    document.getElementById("campo-adultos-alcool").value = c.adultos_bebem_alcool || 0;
    document.getElementById("campo-vegetarianos").value = c.vegetarianos || 0;
    document.getElementById("campo-veganos").value = c.veganos || 0;
    document.getElementById("campo-sem-bovina").value = c.sem_carne_bovina || 0;
    document.getElementById("campo-sem-suina").value = c.sem_carne_suina || 0;
    document.getElementById("campo-lactose").value = c.intolerantes_lactose || 0;
    document.getElementById("campo-alergias").value = c.alergias || "";
    document.getElementById("campo-outras-restricoes").value = c.outras_restricoes || "";
    atualizarContadorTotal();
    atualizarLimites();
    if ([c.vegetarianos, c.veganos, c.sem_carne_bovina, c.sem_carne_suina, c.intolerantes_lactose].some(Number) || c.alergias || c.outras_restricoes) {
        document.getElementById("detalhes-convidados").open = true;
    }
}

function n(id) { return Math.max(0, Number(document.getElementById(id).value) || 0); }
function totalAtual() { return n("campo-adultos") + n("campo-criancas"); }

function atualizarContadorTotal() {
    document.getElementById("total-convidados").textContent = totalAtual();
}

function atualizarLimites() {
    const adultos = n("campo-adultos");
    const total = totalAtual();
    const alcool = document.getElementById("campo-adultos-alcool");
    alcool.max = adultos;
    if (Number(alcool.value) > adultos) alcool.value = adultos;
    CAMPOS_RESTRICOES_NUMERICAS.forEach((id) => {
        const campo = document.getElementById(id);
        campo.max = total;
        if (Number(campo.value) > total) campo.value = total;
    });
}

function isoDataEvento() {
    const valor = document.getElementById("campo-data-evento").value;
    if (!valor) return null;
    const data = new Date(valor);
    return Number.isNaN(data.getTime()) ? null : data.toISOString();
}

function montarParcialPlanejamento(etapaAtual = "planejamento") {
    const adultos = n("campo-adultos");
    const adultosAlcool = Math.min(n("campo-adultos-alcool"), adultos);
    return {
        etapa_atual: etapaAtual,
        evento: {
            nome: document.getElementById("campo-nome").value.trim(),
            data_evento: isoDataEvento(),
            tipo: estadoAtual.evento.tipo,
            duracao_horas: Number(document.getElementById("campo-duracao").value) || 4,
        },
        convidados: {
            adultos,
            criancas: n("campo-criancas"),
            adultos_bebem_alcool: adultosAlcool,
            vegetarianos: n("campo-vegetarianos"),
            veganos: n("campo-veganos"),
            sem_carne_bovina: n("campo-sem-bovina"),
            sem_carne_suina: n("campo-sem-suina"),
            intolerantes_lactose: n("campo-lactose"),
            alergias: document.getElementById("campo-alergias").value.trim(),
            outras_restricoes: document.getElementById("campo-outras-restricoes").value.trim(),
        },
        orcamento_maximo: document.getElementById("campo-orcamento").value === "" ? null : Number(document.getElementById("campo-orcamento").value),
        perfil_consumo: estadoAtual.perfil_consumo,
        perfil_personalizado: estadoAtual.perfil_consumo === "personalizado" ? coletarPerfilPersonalizado() : null,
    };
}

function salvarRascunhoPlanejamento(etapa = estadoAtual.etapa_atual || "planejamento") {
    window.clearTimeout(timerRascunho);
    estadoAtual = EstadoChurrasco.salvar(montarParcialPlanejamento(etapa));
}
function agendarSalvamentoRascunho() { window.clearTimeout(timerRascunho); timerRascunho = window.setTimeout(salvarRascunhoPlanejamento, 180); }

function validarFormulario() {
    const adultos = n("campo-adultos"), criancas = n("campo-criancas"), total = adultos + criancas;
    const duracao = Number(document.getElementById("campo-duracao").value) || 0;
    const alcool = n("campo-adultos-alcool"), vegetarianos = n("campo-vegetarianos"), veganos = n("campo-veganos");
    if (total <= 0) return "Informe ao menos 1 convidado.";
    if (total > 500) return "O total de convidados não pode ultrapassar 500 pessoas.";
    if (duracao < 1 || duracao > 48) return "A duração deve ficar entre 1 e 48 horas.";
    if (alcool > adultos) return "Consumidores de álcool não podem superar o total de adultos.";
    if (vegetarianos + veganos > total) return "A soma de vegetarianos e veganos não pode superar o total de convidados.";
    for (const id of CAMPOS_RESTRICOES_NUMERICAS) if (n(id) > total) return "Nenhuma restrição pode ter mais pessoas do que o total de convidados.";
    if (!estadoAtual.evento.tipo) return "Selecione o tipo de evento.";
    const orcamento = document.getElementById("campo-orcamento").value;
    if (orcamento !== "" && Number(orcamento) < 0) return "O orçamento não pode ser negativo.";
    if (estadoAtual.perfil_consumo === "personalizado" && Object.keys(coletarPerfilPersonalizado()).length === 0) return "Perfil personalizado selecionado: preencha ao menos um coeficiente.";
    return null;
}

document.addEventListener("DOMContentLoaded", () => {
    estadoAtual = EstadoChurrasco.marcarEtapa("planejamento");
    renderizarStepper(document.getElementById("stepper"), "planejamento");
    renderizarOpcoesEvento(); renderizarOpcoesPerfil(); preencherCampos(); preencherCamposPersonalizado();

    ["campo-adultos", "campo-criancas"].forEach((id) => document.getElementById(id).addEventListener("input", () => {
        atualizarContadorTotal(); atualizarLimites(); agendarSalvamentoRascunho();
    }));
    ["campo-adultos-alcool", ...CAMPOS_RESTRICOES_NUMERICAS, "campo-nome", "campo-data-evento", "campo-duracao", "campo-orcamento", "campo-alergias", "campo-outras-restricoes", ...Object.keys(CAMPOS_PERSONALIZADOS)]
        .forEach((id) => document.getElementById(id).addEventListener("input", agendarSalvamentoRascunho));

    window.addEventListener("pagehide", () => { if (document.getElementById("form-planejamento")) salvarRascunhoPlanejamento(); });
    document.getElementById("form-planejamento").addEventListener("submit", (evento) => {
        evento.preventDefault();
        const erro = validarFormulario(), elementoErro = document.getElementById("mensagem-erro");
        if (erro) { mostrarMensagem(elementoErro, erro, "erro"); return; }
        mostrarMensagem(elementoErro, null); window.clearTimeout(timerRascunho);
        estadoAtual = EstadoChurrasco.salvar(montarParcialPlanejamento("carnes"));
        irPara("carnes.html");
    });
});
