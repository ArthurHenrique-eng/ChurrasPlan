/* Ferramentas B2C. A UI apenas apresenta recursos; a autorização é sempre do backend. */
document.addEventListener("DOMContentLoaded", async () => {
    const plano = document.getElementById("conta-beneficios");
    const areaModelos = document.getElementById("conta-modelos");
    const resultado = document.getElementById("conta-resultado-premium");
    if (!plano || !areaModelos || !resultado) return;

    const bloco = (tag, texto, classe) => {
        const e = document.createElement(tag);
        if (texto !== undefined) e.textContent = String(texto);
        if (classe) e.className = classe;
        return e;
    };
    const mostrarErro = (e) => {
        resultado.replaceChildren(bloco("p", e.message || "Não foi possível concluir a operação.", "mensagem"));
    };
    const acao = (titulo, fn) => {
        const b = bloco("button", titulo, "botao botao--secundario");
        b.type = "button";
        b.addEventListener("click", async () => {
            b.disabled = true;
            try { await fn(); } catch (e) { mostrarErro(e); }
            finally { b.disabled = false; }
        });
        return b;
    };
    const exibirLinhas = (titulo, linhas) => {
        resultado.replaceChildren(bloco("h3", titulo));
        const lista = bloco("ul");
        for (const texto of linhas) lista.appendChild(bloco("li", texto));
        resultado.appendChild(lista);
        resultado.scrollIntoView({ behavior: "smooth", block: "nearest" });
    };
    try {
        const direitos = await ChurrasPlanAPI.meusBeneficios();
        const n = direitos.planejamentos;
        plano.textContent = direitos.beneficios_ativos
            ? "Premium ativo — planejamentos salvos ilimitados e ferramentas exclusivas."
            : "Plano Gratuito — " + n.uso + " de " + n.limite +
              " planejamentos salvos. Eventos existentes permanecem acessíveis após atingir o limite.";
        if (!n.pode_criar) plano.appendChild(bloco("p", "Para salvar um novo evento, exclua um planejamento antigo ou assine o Premium."));

        const churrascos = await ChurrasPlanAPI.meusChurrascos();
        const controles = bloco("div", undefined, "history-actions");
        const seletor = document.createElement("select");
        seletor.id = "seletor-evento-premium";
        seletor.setAttribute("aria-label", "Escolher planejamento para ferramentas Premium");
        if (churrascos.length) {
            for (const evento of churrascos) {
                const opt = document.createElement("option");
                opt.value = String(evento.id);
                opt.textContent = evento.nome || "Churrasco #" + evento.id;
                seletor.appendChild(opt);
            }
        } else {
            const opt = document.createElement("option");
            opt.textContent = "Nenhum planejamento salvo";
            seletor.appendChild(opt);
            seletor.disabled = true;
        }
        const selecionado = () => Number(seletor.value);
        if (direitos.beneficios_ativos && churrascos.length) {
            controles.appendChild(seletor);
            controles.appendChild(acao("Análise de custos", async () => {
                const r = await ChurrasPlanAPI.analiseCustosPremium(selecionado());
                const linhas = [
                    "Subtotal conhecido: " + (r.total_estimado_conhecido == null ? "Indisponível" : formatarMoeda(r.total_estimado_conhecido)),
                    r.estimativa_completa ? "Estimativa completa" : "Estimativa parcial; itens sem preço não integram o total.",
                    "Por pessoa: " + (r.custo_conhecido_por_pessoa == null ? "Indisponível" : formatarMoeda(r.custo_conhecido_por_pessoa)),
                    ...r.categorias.map(c => c.categoria + ": " + formatarMoeda(c.total_conhecido) +
                        (c.percentual_do_conhecido == null ? "" : " (" + c.percentual_do_conhecido + "% do conhecido)")),
                    r.aviso,
                ];
                exibirLinhas("Análise detalhada de custos", linhas);
            }));
            controles.appendChild(acao("Comparar ofertas", async () => {
                const r = await ChurrasPlanAPI.comparacaoAvancadaPremium(selecionado());
                exibirLinhas("Comparação avançada", [
                    "Lojas com ofertas: " + r.lojas_com_ofertas,
                    "Lojas com cesta completa: " + r.lojas_com_cesta_completa,
                    r.melhor_cesta_completa ? "Melhor loja completa: " + r.melhor_cesta_completa.estabelecimento_nome +
                        " — " + formatarMoeda(r.melhor_cesta_completa.total) : "Nenhuma loja oferece a lista completa.",
                    r.economia_potencial == null ? "Economia potencial indisponível." :
                        "Economia potencial: " + formatarMoeda(r.economia_potencial),
                    ...r.alternativas_completas.map(c => c.estabelecimento_nome + ": " + formatarMoeda(c.total)),
                    r.observacao,
                ]);
            }));
            controles.appendChild(acao("Exportar PDF", () => {
                window.location.assign("/api/churrascos/" + selecionado() + "/exportar?formato=pdf");
            }));
            controles.appendChild(acao("Exportar CSV", () => {
                window.location.assign("/api/churrascos/" + selecionado() + "/exportar?formato=csv");
            }));
            controles.appendChild(acao("Salvar como modelo", async () => {
                const nomeOriginal = seletor.selectedOptions[0].textContent;
                const nome = window.prompt("Nome para o modelo reutilizável:", nomeOriginal);
                if (!nome) return;
                await ChurrasPlanAPI.criarModeloEvento(selecionado(), nome);
                await atualizarModelos();
                exibirLinhas("Modelo salvo", ["Modelo criado com as escolhas do planejamento."]);
            }));
            plano.parentNode.insertBefore(controles, resultado);
        } else if (!direitos.beneficios_ativos) {
            plano.parentNode.insertBefore(bloco("p", "PDF/CSV de planejamento, comparação avançada, análise detalhada e criação de modelos requerem Premium."), resultado);
        }
        async function atualizarModelos() {
            const modelos = await ChurrasPlanAPI.listarModelosEvento();
            areaModelos.replaceChildren();
            if (!modelos.length) {
                areaModelos.appendChild(bloco("p", "Nenhum modelo salvo."));
                return;
            }
            for (const modelo of modelos) {
                const cartao = bloco("article", undefined, "history-card");
                cartao.appendChild(bloco("strong", modelo.nome));
                const botoes = bloco("div", undefined, "history-actions");
                if (direitos.beneficios_ativos) {
                    botoes.appendChild(acao("Usar modelo", async () => {
                        const evento = await ChurrasPlanAPI.usarModeloEvento(modelo.id);
                        EstadoChurrasco.carregarResultadoSalvo(evento);
                        irPara("resultado.html");
                    }));
                }
                botoes.appendChild(acao("Excluir", async () => {
                    if (!window.confirm("Excluir o modelo? O churrasco original será preservado.")) return;
                    await ChurrasPlanAPI.excluirModeloEvento(modelo.id);
                    await atualizarModelos();
                }));
                cartao.appendChild(botoes);
                areaModelos.appendChild(cartao);
            }
        }
        await atualizarModelos();
    } catch (e) {
        plano.textContent = "Não foi possível consultar os benefícios da conta.";
        areaModelos.textContent = "Não foi possível carregar os modelos.";
        mostrarErro(e);
    }
});
