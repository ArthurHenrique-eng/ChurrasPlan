const NOMES_CATEGORIA = { carne: "Carnes", carvao: "Carvão", bebida: "Bebidas", extra: "Extras", acompanhamento: "Acompanhamentos" };
let dadosResultadoAtuais = null;
let usuarioResultado = null;
let listaComprasAtual = null;

function nomePorChave(catalogo, chave) { return catalogo.find((item) => item.chave === chave)?.nome || String(chave || "").replace(/_/g, " "); }

function montarPayload(estado) {
    const c = estado.convidados;
    return {
        nome: estado.evento.nome || null,
        chave_cliente: estado.planejamento_id,
        data_evento: estado.evento.data_evento || null,
        tipo_evento: estado.evento.tipo,
        duracao_horas: estado.evento.duracao_horas,
        perfil_consumo: estado.perfil_consumo,
        perfil_personalizado: estado.perfil_consumo === "personalizado" ? estado.perfil_personalizado : null,
        adultos: c.adultos,
        adultos_bebem_alcool: c.adultos_bebem_alcool,
        criancas: c.criancas,
        vegetarianos: c.vegetarianos,
        veganos: c.veganos,
        sem_carne_bovina: c.sem_carne_bovina,
        sem_carne_suina: c.sem_carne_suina,
        intolerantes_lactose: c.intolerantes_lactose,
        alergias: c.alergias || null,
        outras_restricoes: c.outras_restricoes || null,
        orcamento_maximo: estado.orcamento_maximo,
        dividir_entre: estado.dividir_entre,
        carnes: estado.carnes.selecionadas,
        carvao_ativo: estado.carvao_ativo !== false,
        bebidas_nao_alcoolicas_ativas: estado.bebidas.nao_alcoolicas_ativas,
        bebida_alcoolica_ativa: estado.bebidas.alcoolica_ativa,
        gelo_ativo: estado.bebidas.gelo_ativo === true,
        extras_ativos: estado.extras_ativos,
        acompanhamentos_ativos: estado.acompanhamentos_ativos,
    };
}

function formatarDataEvento(valor) {
    if (!valor) return null;
    const d = new Date(valor);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleString("pt-BR", { dateStyle: "medium", timeStyle: "short" });
}

function renderizarResumo(dados) {
    const tipoEvento = nomePorChave(TIPOS_EVENTO, dados.tipo_evento), perfil = nomePorChave(PERFIS_CONSUMO, dados.perfil_consumo);
    document.getElementById("resumo-titulo").textContent = dados.nome || `Churrasco para ${dados.total_pessoas} pessoas`;
    const data = formatarDataEvento(dados.data_evento);
    const casasDuracao = Number.isInteger(Number(dados.duracao_horas)) ? 0 : 1;
    document.getElementById("resumo-meta").textContent = [
        `${dados.adultos} adulto(s)`, `${dados.criancas} criança(s)`, `${formatarNumero(dados.duracao_horas, casasDuracao)}h`, tipoEvento, perfil, data,
    ].filter(Boolean).join(" · ");
    document.getElementById("bloco-carne").textContent = `${formatarNumero(dados.carne_total_kg)} kg`;
    document.getElementById("bloco-carvao").textContent = dados.carvao_ativo ? `${formatarNumero(dados.carvao_necessario_kg)} → ${formatarNumero(dados.carvao_compra_kg)} kg` : "não incluído";
    document.getElementById("bloco-pessoas").textContent = dados.total_pessoas;
    const custoPessoaEl = document.getElementById("bloco-custo-pessoa");
    if (dados.custo_por_pessoa != null) {
        custoPessoaEl.textContent = dados.estimativa_precos_completa
            ? formatarMoeda(dados.custo_por_pessoa)
            : `≈ ${formatarMoeda(dados.custo_por_pessoa)}`;
        custoPessoaEl.title = dados.estimativa_precos_completa
            ? "Estimativa completa com preço para todos os itens."
            : `Estimativa parcial: ${dados.itens_sem_preco || 0} item(ns) ainda estão sem preço.`;
    } else {
        custoPessoaEl.textContent = "sem preços";
        custoPessoaEl.title = "Ainda não há nenhuma oferta cadastrada para calcular o custo.";
    }
}

function descricaoCompra(item) {
    const base = `${formatarNumero(item.quantidade_compra)} ${escaparHTML(item.unidade_compra)}`;
    return item.quantidade_embalagens != null ? `${base}<br><small>${item.quantidade_embalagens} ${escaparHTML(item.unidade_venda)}(s)</small>` : base;
}

function renderizarItens(itens) {
    const porCategoria = {};
    itens.forEach((item) => { (porCategoria[item.categoria] ||= []).push(item); });
    let html = "";
    Object.entries(porCategoria).forEach(([categoria, lista]) => {
        html += `<tr><td colspan="5" class="categoria-titulo">${escaparHTML(NOMES_CATEGORIA[categoria] || categoria)}</td></tr>`;
        lista.forEach((item) => {
            const origemPreco = item.preco_fonte === "referencia_brasil_2026"
                ? '<br><small>Referência Brasil 2026</small>'
                : (item.estabelecimento_nome ? `<br><small>${escaparHTML(item.estabelecimento_nome)}</small>` : "");
            const preco = item.preco_estimado != null
                ? `${formatarMoeda(item.preco_estimado)} / ${escaparHTML(item.unidade_venda)}${origemPreco}`
                : `<span class="sem-preco">sem referência</span>`;
            html += `<tr><td>${escaparHTML(item.nome)}</td><td class="numero">${formatarNumero(item.quantidade_necessaria)} ${escaparHTML(item.unidade_necessaria)}</td><td class="numero">${descricaoCompra(item)}</td><td class="numero">${preco}</td><td class="numero">${item.subtotal_estimado != null ? formatarMoeda(item.subtotal_estimado) : "-"}</td></tr>`;
        });
    });
    document.getElementById("tabela-itens-corpo").innerHTML = html || `<tr><td colspan="5" class="texto-suave">Nenhum item calculado.</td></tr>`;
}

function renderizarCustos(dados) {
    const temEstimativa = dados.custo_total_estimado != null;
    const rotuloTotal = dados.estimativa_precos_completa ? "Custo da compra estimada" : "Subtotal com preços disponíveis";
    const rotuloPessoa = dados.estimativa_precos_completa ? "Custo por pessoa" : "Custo por pessoa (parcial)";
    const custoPessoa = dados.custo_por_pessoa != null ? formatarMoeda(dados.custo_por_pessoa) : "sem preços cadastrados";
    const total = temEstimativa ? formatarMoeda(dados.custo_total_estimado) : "sem preços cadastrados";
    document.getElementById("bloco-custos").innerHTML = `<div class="custos-linha"><span>${rotuloTotal}</span><span>${total}</span></div><div class="custos-linha total"><span>${rotuloPessoa}</span><span>${custoPessoa}</span></div>`;
    const avisoEl = document.getElementById("mensagem-precos");
    dados.aviso_precos ? mostrarMensagem(avisoEl, dados.aviso_precos, "aviso") : mostrarMensagem(avisoEl, null);
}

function renderizarOrcamento(dados) {
    const el = document.getElementById("bloco-orcamento");
    if (dados.orcamento_maximo == null) {
        el.innerHTML = `<p class="texto-suave">Você não definiu um orçamento máximo. <a class="inline-link" href="planejamento.html">Adicionar orçamento</a></p>`;
        return;
    }
    let status = "Ainda não há preços suficientes para comparar o orçamento.", classe = "budget-neutral";
    let rotuloEstimativa = "Estimativa atual";
    if (dados.orcamento_status === "estimativa_parcial") {
        status = `${dados.itens_sem_preco || 0} item(ns) ainda estão sem preço. O subtotal conhecido não permite afirmar se o orçamento será suficiente.`;
        rotuloEstimativa = "Subtotal conhecido";
    }
    if (dados.orcamento_status === "dentro") { status = `Restante: ${formatarMoeda(Math.max(0, dados.orcamento_diferenca || 0))}`; classe = "budget-ok"; }
    if (dados.orcamento_status === "acima") { status = `Acima do orçamento em ${formatarMoeda(Math.abs(dados.orcamento_diferenca || 0))}`; classe = "budget-over"; }
    el.innerHTML = `<div class="budget-result ${classe}"><div><span>Orçamento disponível</span><strong>${formatarMoeda(dados.orcamento_maximo)}</strong></div><div><span>${rotuloEstimativa}</span><strong>${formatarMoeda(dados.custo_total_estimado)}</strong></div><p>${escaparHTML(status)}</p></div>`;
}

function renderizarRestricoes(dados) {
    const el = document.getElementById("bloco-restricoes");
    const chips = [];
    if (dados.vegetarianos) chips.push(`${dados.vegetarianos} vegetariano(s)`);
    if (dados.veganos) chips.push(`${dados.veganos} vegano(s)`);
    if (dados.sem_carne_bovina) chips.push(`${dados.sem_carne_bovina} sem bovina`);
    if (dados.sem_carne_suina) chips.push(`${dados.sem_carne_suina} sem suína`);
    if (dados.intolerantes_lactose) chips.push(`${dados.intolerantes_lactose} com intolerância à lactose`);
    const avisos = (dados.avisos_restricoes || []).map((a) => `<li>${escaparHTML(a)}</li>`).join("");
    el.innerHTML = chips.length || avisos || dados.alergias || dados.outras_restricoes
        ? `<div class="restriction-chips">${chips.map((x) => `<span>${escaparHTML(x)}</span>`).join("")}</div>${dados.alergias ? `<p><strong>Alergias:</strong> ${escaparHTML(dados.alergias)}</p>` : ""}${dados.outras_restricoes ? `<p><strong>Outras:</strong> ${escaparHTML(dados.outras_restricoes)}</p>` : ""}${avisos ? `<ul class="restriction-warnings">${avisos}</ul>` : ""}`
        : `<p class="texto-suave">Nenhuma restrição alimentar foi informada.</p>`;
}

function criarDialogPreco() {
    if (document.getElementById("dialog-preco-pago")) return;
    const dialog = document.createElement("dialog");
    dialog.id = "dialog-preco-pago"; dialog.className = "price-dialog";
    dialog.innerHTML = `<form method="dialog" class="price-dialog__box"><button value="cancel" class="dialog-close" aria-label="Fechar">×</button><span class="eyebrow"><span></span>COMPRA REAL</span><h2 id="dialog-item-nome">Item</h2><p id="dialog-item-estimado" class="texto-suave"></p><label class="campo"><span>Quanto você pagou no total?</span><div class="money-field money-field--dialog"><span>R$</span><input id="dialog-valor-pago" min="0" step="0.01" inputmode="decimal" type="number" placeholder="0,00"></div></label><small>Você pode deixar em branco para apenas marcar como comprado.</small><div class="dialog-actions"><button value="cancel" class="botao botao--secundario">Cancelar</button><button value="confirm" class="botao botao--primario">Marcar como comprado</button></div></form>`;
    document.body.appendChild(dialog);
}

async function pedirValorPago(item) {
    criarDialogPreco();
    const dialog = document.getElementById("dialog-preco-pago");
    document.getElementById("dialog-item-nome").textContent = item.descricao;
    document.getElementById("dialog-item-estimado").textContent = item.subtotal_estimado != null ? `Estimativa: ${formatarMoeda(item.subtotal_estimado)}` : "Este item não possui estimativa de preço.";
    const input = document.getElementById("dialog-valor-pago"); input.value = item.valor_pago_total ?? "";
    return new Promise((resolve) => {
        dialog.addEventListener("close", () => {
            if (dialog.returnValue !== "confirm") { resolve({ confirmado: false }); return; }
            const valor = input.value === "" ? null : Number(input.value);
            resolve({ confirmado: true, valor: Number.isFinite(valor) ? valor : null });
        }, { once: true });
        dialog.showModal(); input.focus();
    });
}

function renderizarTotaisLista(lista) {
    document.getElementById("lista-progresso-badge").textContent = `${lista.itens_comprados} / ${lista.itens_total}`;
    const economia = lista.economia_real == null ? "—" : formatarMoeda(lista.economia_real);
    const rotuloEstimativa = lista.estimativa_completa ? "Estimativa original" : "Estimativa parcial";
    const statusReal = lista.valor_pago_completo ? "Valor real final" : `Valor informado (${lista.itens_com_valor_pago || 0}/${lista.itens_total || 0})`;
    const nota = !lista.estimativa_completa
        ? `<p class="shopping-total-note">${lista.itens_sem_preco || 0} item(ns) ainda não possuem preço estimado. A economia só é calculada quando estimativa e valores pagos estão completos.</p>`
        : (!lista.valor_pago_completo && lista.itens_comprados === lista.itens_total && lista.itens_total > 0
            ? `<p class="shopping-total-note">Todos os itens foram marcados, mas ainda faltam valores pagos para fechar o custo real.</p>` : "");
    document.getElementById("lista-totais").innerHTML = `<div><span>${rotuloEstimativa}</span><strong>${formatarMoeda(lista.total_estimado)}</strong></div><div><span>${statusReal}</span><strong>${formatarMoeda(lista.total_pago)}</strong></div><div><span>Economia final</span><strong>${economia}</strong></div><div class="shopping-progress"><span style="width:${Math.max(0, Math.min(100, lista.progresso_percentual || 0))}%"></span></div>${nota}`;
}

async function carregarListaCompras(churrascoId) {
    const container = document.getElementById("lista-compras-corpo");
    try {
        const lista = await ChurrasPlanAPI.obterListaCompras(churrascoId);
        listaComprasAtual = lista;
        renderizarTotaisLista(lista);
        if (dadosResultadoAtuais) atualizarValorDivisao(dadosResultadoAtuais);
        const porCategoria = {}; lista.itens.forEach((item) => { (porCategoria[item.categoria] ||= []).push(item); });
        let html = "";
        Object.entries(porCategoria).forEach(([categoria, itens]) => {
            html += `<div class="categoria-titulo">${escaparHTML(NOMES_CATEGORIA[categoria] || categoria)}</div>`;
            itens.forEach((item) => {
                const embalagens = item.quantidade_embalagens != null ? ` · ${item.quantidade_embalagens} ${escaparHTML(item.unidade_venda)}(s)` : "";
                const financeiro = item.comprado && item.valor_pago_total != null ? `<span class="paid-tag">Pago: ${formatarMoeda(item.valor_pago_total)}</span>` : (item.subtotal_estimado != null ? `<span>Estimado: ${formatarMoeda(item.subtotal_estimado)}</span>` : "");
                html += `<div class="lista-compras-item shopping-check-item ${item.comprado ? "comprado" : ""}" data-item-id="${Number(item.id)}"><input type="checkbox" ${item.comprado ? "checked" : ""} aria-label="Marcar ${escaparHTML(item.descricao)} como comprado"><span class="lista-compras-item__desc"><strong>${escaparHTML(item.descricao)}</strong><small>${formatarNumero(item.quantidade)} ${escaparHTML(item.unidade)}${embalagens}</small></span><span class="lista-compras-item__qtd">${financeiro}</span></div>`;
            });
        });
        container.innerHTML = html || `<p class="texto-suave">A lista de compras está vazia.</p>`;
        container.querySelectorAll(".shopping-check-item").forEach((linha) => {
            const checkbox = linha.querySelector("input[type=checkbox]");
            const item = lista.itens.find((x) => String(x.id) === linha.dataset.itemId);
            checkbox.addEventListener("change", async () => {
                const novoValor = checkbox.checked; checkbox.disabled = true;
                try {
                    if (novoValor) {
                        const resposta = await pedirValorPago(item);
                        if (!resposta.confirmado) { checkbox.checked = false; return; }
                        await ChurrasPlanAPI.atualizarItemListaCompras(item.id, { comprado: true, valor_pago_total: resposta.valor, estabelecimento_compra_id: item.estabelecimento_compra_id });
                    } else {
                        await ChurrasPlanAPI.atualizarItemListaCompras(item.id, { comprado: false, valor_pago_total: null, estabelecimento_compra_id: null });
                    }
                    await carregarListaCompras(churrascoId);
                } catch (erro) {
                    checkbox.checked = !novoValor;
                    mostrarMensagem(document.getElementById("mensagem-erro-geral"), `Não foi possível atualizar a compra: ${erro.message}`, "erro");
                } finally { checkbox.disabled = false; }
            });
        });
    } catch {
        container.innerHTML = `<p class="texto-suave">Não foi possível carregar a lista de compras.</p>`;
    }
}

async function obterResultado(estado) {
    const payload = montarPayload(estado);
    if (estado.churrasco_id && !estado.resultado_desatualizado) {
        try { return await ChurrasPlanAPI.obterChurrasco(estado.churrasco_id); } catch (erro) { if (erro.status !== 404) throw erro; }
    }
    if (estado.churrasco_id) {
        try { return await ChurrasPlanAPI.atualizarChurrasco(estado.churrasco_id, payload); } catch (erro) { if (erro.status !== 404) throw erro; }
    }
    return ChurrasPlanAPI.criarChurrasco(payload);
}

function obterBaseDivisao(dados) {
    if (listaComprasAtual?.valor_pago_completo) {
        return { valor: Number(listaComprasAtual.total_pago), rotulo: "valor real registrado" };
    }
    if (dados.custo_total_estimado != null) {
        return {
            valor: Number(dados.custo_total_estimado),
            rotulo: dados.estimativa_precos_completa ? "estimativa completa" : "subtotal estimado (parcial)",
        };
    }
    return { valor: null, rotulo: "sem preços cadastrados" };
}

function atualizarValorDivisao(dados) {
    const input = document.getElementById("divisao-pessoas");
    if (!input) return;
    const total = Math.max(2, dados.total_pessoas || 2);
    const n = Math.max(2, Math.min(total, Number(input.value) || 2));
    input.value = n;
    const base = obterBaseDivisao(dados);
    document.getElementById("divisao-valor").textContent = base.valor == null ? "indisponível" : formatarMoeda(base.valor / n);
    const baseEl = document.getElementById("divisao-base");
    if (baseEl) baseEl.textContent = base.rotulo;
}

async function configurarDivisao(dados) {
    const input = document.getElementById("divisao-pessoas"), total = Math.max(2, dados.total_pessoas || 2);
    input.max = total; input.value = Math.min(total, dados.dividir_entre || 2);
    let timer;
    const salvar = () => {
        atualizarValorDivisao(dados);
        EstadoChurrasco.salvar({ dividir_entre: Number(input.value) }, { invalidarResultado: false });
        clearTimeout(timer); timer = setTimeout(async () => { try { await ChurrasPlanAPI.atualizarDivisao(dados.id, Number(input.value)); } catch { /* divisão local continua utilizável */ } }, 250);
    };
    document.getElementById("divisao-menos").onclick = () => { input.value = Math.max(2, Number(input.value) - 1); salvar(); };
    document.getElementById("divisao-mais").onclick = () => { input.value = Math.min(total, Number(input.value) + 1); salvar(); };
    input.oninput = salvar; atualizarValorDivisao(dados);
}

async function renderizarRecursosConta(dados) {
    usuarioResultado = await ChurrasPlanAuth.usuarioAtual().catch(() => null);
    const stateEl = document.getElementById("central-account-state"), copy = document.getElementById("advanced-hub-copy");
    if (!usuarioResultado) {
        stateEl.textContent = "Não salvo em uma conta";
        copy.innerHTML = `Você pode usar toda a calculadora sem cadastro. Para convites, histórico e mapa, <a class="inline-link" href="${ChurrasPlanAuth.urlLogin("resultado.html")}">entre ou crie sua conta</a>.`;
        ["lock-convidados", "lock-mapa", "lock-historico"].forEach((id) => { document.getElementById(id).hidden = false; });
        document.getElementById("acao-convidados").onclick = () => irPara(ChurrasPlanAuth.urlLogin("resultado.html"));
        document.getElementById("acao-onde-comprar").onclick = () => irPara(ChurrasPlanAuth.urlLogin("resultado.html"));
        document.getElementById("acao-historico").href = ChurrasPlanAuth.urlLogin("minha-conta.html");
        return;
    }
    try { await ChurrasPlanAuth.vincularPlanejamentoAtual(); } catch { /* convite mostrará erro se vínculo falhar */ }
    stateEl.textContent = `Salvo na conta de ${usuarioResultado.nome.split(" ")[0]}`;
    copy.textContent = "Este churrasco está vinculado à sua conta. Você pode convidar pessoas, consultar o histórico e comparar onde comprar.";
    ["lock-convidados", "lock-mapa", "lock-historico"].forEach((id) => { document.getElementById(id).hidden = true; });
    document.getElementById("acao-onde-comprar").onclick = () => irPara(`onde-comprar.html?churrasco=${dados.id}`);
    document.getElementById("acao-convidados").onclick = () => abrirPainelConvite(dados.id);
}

async function abrirPainelConvite(churrascoId) {
    const painel = document.getElementById("painel-convite"); painel.hidden = false; painel.innerHTML = `<p class="texto-suave">Preparando seu link...</p>`;
    try {
        const [convite, resumo] = await Promise.all([ChurrasPlanAPI.criarConvite(churrascoId), ChurrasPlanAPI.resumoConvite(churrascoId)]);
        const conviteUrl = new URL(
            `convite.html?codigo=${encodeURIComponent(convite.codigo)}`,
            window.location.href,
        ).href;
        const ambienteLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
        const avisoLocal = ambienteLocal
            ? '<p class="mensagem mensagem--aviso">Este link usa o endereço local deste computador. Para abrir em outro celular/computador durante o desenvolvimento, acesse o ChurrasPlan por um endereço da rede local ou pelo domínio público.</p>'
            : "";
        painel.innerHTML = `<div class="invite-head"><div><span class="eyebrow"><span></span>LINK PARA CONVIDADOS</span><h3>Confirmação de presença</h3></div><div class="invite-head__actions"><button class="botao botao--secundario" id="abrir-convite" type="button">Abrir convite</button><button class="botao botao--secundario" id="copiar-convite" type="button">Copiar link</button>${navigator.share ? '<button class="botao botao--secundario" id="compartilhar-convite" type="button">Compartilhar</button>' : ""}</div></div><div class="invite-link"><input readonly value="${escaparHTML(conviteUrl)}" id="input-convite-url"></div>${avisoLocal}<div class="invite-stats"><div><strong>${resumo.confirmados}</strong><span>confirmados</span></div><div><strong>${resumo.talvez}</strong><span>talvez</span></div><div><strong>${resumo.nao}</strong><span>não vão</span></div><div><strong>${resumo.total_respostas}</strong><span>respostas</span></div></div>${resumo.confirmados > 0 ? `<button class="botao botao--primario" type="button" id="aplicar-confirmados">Recalcular usando confirmados</button>` : `<p class="texto-suave">Quando houver confirmações, você poderá recalcular o planejamento com os dados reais.</p>`}<div class="rsvp-mini-list">${resumo.respostas.slice(0, 8).map((r) => `<span><strong>${escaparHTML(r.nome)}</strong> · ${r.resposta === "confirmado" ? "vai" : r.resposta}</span>`).join("")}</div>`;
        document.getElementById("abrir-convite").onclick = () => window.open(conviteUrl, "_blank", "noopener");
        document.getElementById("copiar-convite").onclick = async () => {
            try { await navigator.clipboard.writeText(conviteUrl); } catch { document.getElementById("input-convite-url").select(); document.execCommand("copy"); }
            document.getElementById("copiar-convite").textContent = "Copiado ✓";
        };
        const compartilhar = document.getElementById("compartilhar-convite");
        if (compartilhar) compartilhar.onclick = async () => {
            try {
                await navigator.share({
                    title: convite.nome_churrasco || "Convite ChurrasPlan",
                    text: "Você foi convidado para um churrasco. Confirme sua presença no ChurrasPlan.",
                    url: conviteUrl,
                });
            } catch (erro) {
                if (erro?.name !== "AbortError") {
                    painel.insertAdjacentHTML("beforeend", `<p class="mensagem mensagem--erro">${escaparHTML(erro.message || "Não foi possível compartilhar o convite.")}</p>`);
                }
            }
        };
        const aplicar = document.getElementById("aplicar-confirmados");
        if (aplicar) aplicar.onclick = async () => {
            aplicar.disabled = true; aplicar.textContent = "Recalculando...";
            try {
                const novo = await ChurrasPlanAPI.aplicarConfirmados(churrascoId); dadosResultadoAtuais = novo;
                EstadoChurrasco.salvar({ convidados: { adultos: novo.adultos, criancas: novo.criancas, adultos_bebem_alcool: novo.adultos_bebem_alcool, vegetarianos: novo.vegetarianos, veganos: novo.veganos, sem_carne_bovina: novo.sem_carne_bovina, sem_carne_suina: novo.sem_carne_suina, intolerantes_lactose: novo.intolerantes_lactose, alergias: novo.alergias || "", outras_restricoes: novo.outras_restricoes || "" }, resultado_desatualizado: false }, { invalidarResultado: false });
                renderizarTudo(novo); await carregarListaCompras(novo.id); await abrirPainelConvite(novo.id);
            } catch (erro) { painel.insertAdjacentHTML("beforeend", `<p class="mensagem mensagem--erro">${escaparHTML(erro.message)}</p>`); }
        };
    } catch (erro) { painel.innerHTML = `<p class="mensagem mensagem--erro">${escaparHTML(erro.message)}</p>`; }
}

function renderizarTudo(dados) {
    renderizarResumo(dados); renderizarItens(dados.itens || []); renderizarCustos(dados); renderizarOrcamento(dados); renderizarRestricoes(dados); configurarDivisao(dados);
}

document.addEventListener("DOMContentLoaded", async () => {
    let estado = EstadoChurrasco.obter();
    if (EstadoChurrasco.totalPessoas() === 0) { irPara("planejamento.html"); return; }
    if (!estado.carnes.selecionadas.length) { irPara("carnes.html"); return; }
    estado = EstadoChurrasco.marcarEtapa("resultado"); renderizarStepper(document.getElementById("stepper"), "resultado");
    const carregando = document.getElementById("carregando"), conteudo = document.getElementById("conteudo-resultado"), erroEl = document.getElementById("mensagem-erro-geral");
    try {
        const dados = await obterResultado(estado); dadosResultadoAtuais = dados;
        EstadoChurrasco.salvar({ churrasco_id: dados.id, resultado_desatualizado: false, etapa_atual: "resultado" }, { invalidarResultado: false });
        renderizarTudo(dados); await carregarListaCompras(dados.id); await renderizarRecursosConta(dados);
        carregando.style.display = "none"; conteudo.style.display = "block";
    } catch (erro) { carregando.style.display = "none"; mostrarMensagem(erroEl, `Não foi possível calcular o churrasco: ${erro.message}`, "erro"); }

    document.getElementById("botao-refazer").addEventListener("click", () => { EstadoChurrasco.limpar(); irPara("planejamento.html"); });
    document.getElementById("botao-concluir").addEventListener("click", () => { EstadoChurrasco.limpar(); irPara("index.html"); });
});
