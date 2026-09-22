/**
 * script.js
 * Funcoes compartilhadas por todas as paginas do fluxo: renderizar o
 * stepper de progresso, formatar numeros e mostrar mensagens de erro.
 * Incluido em toda pagina, logo depois de config/state/api.
 */

const ETAPAS_FLUXO = [
    { id: "planejamento", rotulo: "Planejamento", pagina: "planejamento.html" },
    { id: "carnes", rotulo: "Carnes", pagina: "carnes.html" },
    { id: "bebidas", rotulo: "Bebidas", pagina: "bebidas.html" },
    { id: "extras", rotulo: "Extras", pagina: "extras.html" },
    { id: "resultado", rotulo: "Resultado", pagina: "resultado.html" },
];

function renderizarStepper(elemento, etapaAtualId) {
    const indiceAtual = ETAPAS_FLUXO.findIndex((e) => e.id === etapaAtualId);
    elemento.className = "steps";
    elemento.setAttribute("aria-label", "Etapas do planejamento");
    elemento.innerHTML = ETAPAS_FLUXO.map((etapa, indice) => {
        const classes = [indice < indiceAtual ? "done" : "", indice === indiceAtual ? "active" : ""].filter(Boolean).join(" ");
        const conteudo = `<span class="step-number">${String(indice + 1).padStart(2, "0")}</span><span class="step-label">${etapa.rotulo}</span>`;
        // Não libera etapas futuras antes de o usuário chegar nelas; etapas anteriores funcionam como navegação.
        const link = indice <= indiceAtual
            ? `<a href="${etapa.pagina}" ${indice === indiceAtual ? 'aria-current="step"' : ""}>${conteudo}</a>`
            : `<span class="step-link" aria-disabled="true">${conteudo}</span>`;
        return `<li class="${classes}">${link}</li>`;
    }).join("");
}

function formatarNumero(valor, casas = 2) {
    if (valor === null || valor === undefined) return "-";
    return Number(valor).toLocaleString("pt-BR", {
        minimumFractionDigits: casas, maximumFractionDigits: casas,
    });
}

function formatarMoeda(valor) {
    if (valor === null || valor === undefined) return "sem preço cadastrado";
    return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function mostrarMensagem(elemento, texto, tipo = "erro") {
    if (!texto) {
        elemento.innerHTML = "";
        elemento.style.display = "none";
        return;
    }
    elemento.style.display = "block";
    elemento.className = `mensagem mensagem--${tipo}`;
    elemento.textContent = texto;
}

function irPara(pagina) {
    window.location.href = pagina;
}

function escaparHTML(valor) {
    return String(valor ?? "").replace(/[&<>'"]/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;"
    }[c]));
}
