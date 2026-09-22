/**
 * index.js - pagina inicial
 * Se já existe um planejamento em andamento, o atalho continua da etapa
 * mais recente em vez de sempre voltar ao começo.
 */
const PAGINAS_ETAPA = {
    planejamento: "planejamento.html",
    carnes: "carnes.html",
    bebidas: "bebidas.html",
    extras: "extras.html",
    resultado: "resultado.html",
};

function etapaContinuacao(estado) {
    const total = (estado.convidados.adultos || 0) + (estado.convidados.criancas || 0);
    if (total <= 0) return "planejamento";
    if (!estado.carnes?.selecionadas?.length) return "carnes";
    return PAGINAS_ETAPA[estado.etapa_atual] ? estado.etapa_atual : "bebidas";
}

document.addEventListener("DOMContentLoaded", () => {
    const estado = EstadoChurrasco.obter();
    const totalPessoas = EstadoChurrasco.totalPessoas();
    const linkContinuar = document.getElementById("link-continuar");

    if (linkContinuar && totalPessoas > 0) {
        const etapa = etapaContinuacao(estado);
        linkContinuar.href = PAGINAS_ETAPA[etapa];
        linkContinuar.style.display = "inline-flex";
        linkContinuar.textContent = `Continuar planejamento (${totalPessoas} pessoas)`;
    }
});
