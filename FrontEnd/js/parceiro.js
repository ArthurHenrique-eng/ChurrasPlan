let parceiroUsuario = null, parceiroEstabelecimentos = [], parceiroProdutos = [], genericos = [];
let falhaCatalogoGenerico = false;
function isoInput(id) { const v = document.getElementById(id).value; return v ? new Date(v).toISOString() : null; }
function mensagemParceiro(t, tipo="sucesso") { mostrarMensagem(document.getElementById("parceiro-mensagem"), t, tipo); }
function coordenadaFormulario(id, limite) {
    const campo = document.getElementById(id), bruto = campo.value.trim();
    if (!bruto) return null;
    const valor = Number(bruto.replace(",", "."));
    if (!Number.isFinite(valor)) throw new Error("Coordenada inválida. Informe graus decimais.");
    if (Math.abs(valor) > limite) throw new Error(`Coordenada fora do intervalo permitido (-${limite} a ${limite}). Use graus decimais, como -19,959383.`);
    campo.value = String(valor);
    return valor;
}
async function localizarEnderecoEstabelecimento() {
    const partes = ["est-endereco","est-cidade","est-estado","est-cep"].map(id=>document.getElementById(id).value.trim()).filter(Boolean);
    if (!partes.length) throw new Error("Informe pelo menos o endereço ou a cidade para localizar.");
    const resultados = await ChurrasPlanAPI.autocompleteEndereco(partes.join(", "), null, null, 1);
    if (!resultados.length) throw new Error("Não foi possível localizar esse endereço.");
    const item = resultados[0];
    document.getElementById("est-endereco").value = item.label;
    document.getElementById("est-lat").value = item.latitude;
    document.getElementById("est-lng").value = item.longitude;
    return item;
}
function nomeCategoriaGenerico(produto) {
    return produto.categoria_nome || produto.categoria_tipo || "Outros";
}
function renderProdutosGenericos() {
    const categoria = document.getElementById("prod-categoria").value;
    const select = document.getElementById("prod-pai");
    if (!categoria) {
        select.disabled = true;
        select.innerHTML = '<option value="">Selecione a categoria primeiro...</option>';
        return;
    }
    const itens = genericos
        .filter((p) => nomeCategoriaGenerico(p) === categoria)
        .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
    select.disabled = itens.length === 0;
    select.innerHTML = itens.length ? '<option value="">Selecione...</option>'
        + itens.map((p) => {
            const embalagem = !p.venda_fracionada && p.quantidade_embalagem != null && p.unidade_embalagem
                ? ` de ${Number(p.quantidade_embalagem).toLocaleString("pt-BR")} ${escaparHTML(p.unidade_embalagem)}`
                : "";
            const referencia = p.preco_referencia != null && p.preco_referencia_unidade
                ? ` — ref. estimada R$ ${Number(p.preco_referencia).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/${escaparHTML(p.preco_referencia_unidade)}${embalagem}`
                : "";
            return `<option value="${p.id}">${escaparHTML(p.nome)}${referencia}</option>`;
        }).join("")
        : '<option value="">Nenhum produto disponível nesta categoria</option>';
}
function renderCatalogoGenerico() {
    const categorias = [...new Set(genericos.map(nomeCategoriaGenerico))]
        .sort((a, b) => a.localeCompare(b, "pt-BR"));
    const selectCategoria = document.getElementById("prod-categoria");
    selectCategoria.innerHTML = '<option value="">Selecione...</option>'
        + categorias.map((nome) => `<option value="${escaparHTML(nome)}">${escaparHTML(nome)}</option>`).join("");
    renderProdutosGenericos();

    const ajuda = document.getElementById("prod-catalogo-ajuda");
    if (falhaCatalogoGenerico) {
        ajuda.textContent = "Falha ao consultar o catálogo. Confira a conexão e atualize a página; não é necessário recriar produtos.";
    } else if (!genericos.length) {
        ajuda.textContent = "Nenhum produto genérico ativo encontrado. Verifique as migrations do catálogo.";
    } else {
        ajuda.textContent = `${genericos.length} tipos em ${categorias.length} categorias. Referências de set/2026 são estimativas de planejamento, não ofertas reais.`;
    }
}
async function carregarParceiro() {
    // Uma falha em métricas/ofertas não pode esvaziar o seletor de produtos.
    const [dashResult, estsResult, prodsResult, gensResult] = await Promise.allSettled([
        ChurrasPlanAPI.dashboardParceiro(), ChurrasPlanAPI.estabelecimentosParceiro(),
        ChurrasPlanAPI.produtosParceiro(), ChurrasPlanAPI.listarGenericos(),
    ]);
    const dash = dashResult.status === "fulfilled" ? dashResult.value : null;
    const ests = estsResult.status === "fulfilled" ? estsResult.value : [];
    const prods = prodsResult.status === "fulfilled" ? prodsResult.value : [];
    const gens = gensResult.status === "fulfilled" ? gensResult.value : [];
    falhaCatalogoGenerico = gensResult.status === "rejected";
    parceiroEstabelecimentos=ests; parceiroProdutos=prods; genericos=gens;
    const falhas = ["métricas", "estabelecimentos", "produtos comerciais", "catálogo genérico"]
        .filter((_, i) => [dashResult, estsResult, prodsResult, gensResult][i].status === "rejected");
    if (falhas.length) mensagemParceiro(`Falha ao carregar: ${falhas.join(", ")}. Atualize a página para tentar novamente.`, "erro");
    document.getElementById("parceiro-stats").innerHTML = dash ? `<div class="partner-stat"><strong>${dash.estabelecimentos}</strong><span>estabelecimentos</span></div><div class="partner-stat"><strong>${dash.estabelecimentos_verificados}</strong><span>verificados</span></div><div class="partner-stat"><strong>${dash.ofertas_cadastradas}</strong><span>ofertas cadastradas</span></div><div class="partner-stat"><strong>${dash.visualizacoes || 0}</strong><span>visualizações</span></div><div class="partner-stat"><strong>${dash.cliques || 0}</strong><span>cliques em rota</span></div>` : '<div class="empty-state">Falha ao carregar métricas.</div>';
    document.getElementById("parceiro-note").textContent = dash ? dash.mensagem_verificacao : "";
    document.getElementById("lista-estabelecimentos").innerHTML = estsResult.status === "rejected" ? '<div class="empty-state">Falha ao carregar estabelecimentos.</div>' : ests.length ? ests.map(e=>`<div class="basket-row"><strong>${escaparHTML(e.nome)}</strong><br><small>${escaparHTML(e.cidade||e.endereco||e.tipo)} · ${e.parceiro_verificado?'verificado':'aguardando verificação'}</small></div>`).join('') : '<div class="empty-state">Cadastre seu primeiro estabelecimento.</div>';
    document.getElementById("lista-produtos").innerHTML = prodsResult.status === "rejected" ? '<div class="empty-state">Falha ao carregar produtos comerciais.</div>' : prods.length ? prods.map(p=>`<div class="basket-row"><strong>${escaparHTML([p.marca,p.nome].filter(Boolean).join(' — '))}</strong><br><small>${p.quantidade_embalagem||''} ${escaparHTML(p.unidade_embalagem||'')} · ${escaparHTML(p.ean||'sem EAN')}</small></div>`).join('') : '<div class="empty-state">Nenhum SKU comercial cadastrado.</div>';
    const optionsEst = '<option value="">Selecione...</option>'+ests.map(e=>`<option value="${e.id}">${escaparHTML(e.nome)}</option>`).join(''); document.getElementById("preco-est").innerHTML=optionsEst;
    renderCatalogoGenerico();
    document.getElementById("preco-prod").innerHTML='<option value="">Selecione...</option>'+prods.map(p=>`<option value="${p.id}">${escaparHTML([p.marca,p.nome].filter(Boolean).join(' — '))}</option>`).join('');
}
document.addEventListener("DOMContentLoaded", async()=>{
    parceiroUsuario=await ChurrasPlanAuth.usuarioAtual().catch(()=>null);
    if(!parceiroUsuario){irPara(ChurrasPlanAuth.urlLogin("parceiro.html"+window.location.search));return;}
    // O token somente existe no link enviado ao destinatário. Não salvar em storage.
    const tokenConvite = new URLSearchParams(window.location.search).get("convite");
    if(tokenConvite){
        // Limpa antes de chamar API para reduzir exposição do segredo no Referer.
        window.history.replaceState({}, "", window.location.pathname);
        try {
            const aceite = await ChurrasPlanAPI.aceitarConviteOrganizacao(tokenConvite);
            ChurrasPlanAuth.limparCache();
            parceiroUsuario = await ChurrasPlanAuth.usuarioAtual(true);
            try { sessionStorage.setItem("churrasplan_organizacao_id", String(aceite.organizacao_id)); } catch { /* opcional */ }
            mensagemParceiro("Convite aceito. Sua organização já está disponível.");
        } catch(e) { mensagemParceiro(e.message,"erro"); }

    }
    const ativar=document.getElementById("ativar-parceiro"), conteudo=document.getElementById("parceiro-conteudo");
    if(!["parceiro","admin"].includes(parceiroUsuario.papel)){
        ativar.hidden=false;
        ativar.onclick=async()=>{ativar.disabled=true;try{await ChurrasPlanAPI.ativarParceiro();ChurrasPlanAuth.limparCache();location.reload();}catch(e){mensagemParceiro(e.message,"erro");ativar.disabled=false;}};
        return;
    }
    try {
        ChurrasPlanOperacao.iniciar();
        ChurrasPlanComercial.iniciar();
        ChurrasPlanBilling.iniciar();
        await ChurrasPlanEquipe.iniciar(parceiroUsuario, async () => {
            await carregarParceiro();
            try { await ChurrasPlanComercial.carregar(); } catch (erro) { mensagemParceiro(erro.message, "erro"); }
            try { await ChurrasPlanBilling.carregar(); } catch (erro) { mensagemParceiro(erro.message, "erro"); }
            try { await ChurrasPlanOperacao.carregar(); }
            catch (erro) { mensagemParceiro(`Falha ao carregar a operação B2B: ${erro.message}`, "erro"); }
        });
        conteudo.hidden=false;
    } catch(e) { conteudo.hidden=true; mensagemParceiro(e.message,"erro"); return; }
    document.getElementById("prod-categoria").addEventListener("change", renderProdutosGenericos);
    document.getElementById("est-localizar-endereco").onclick=async()=>{const b=document.getElementById("est-localizar-endereco");b.disabled=true;try{await localizarEnderecoEstabelecimento();mensagemParceiro("Endereço localizado e coordenadas preenchidas.");}catch(er){mensagemParceiro(er.message,"erro");}finally{b.disabled=false;}};
    document.getElementById("form-estabelecimento").onsubmit=async(e)=>{e.preventDefault();try{
        let latitude=coordenadaFormulario("est-lat",90), longitude=coordenadaFormulario("est-lng",180);
        if((latitude===null||longitude===null)&&document.getElementById("est-endereco").value.trim()){await localizarEnderecoEstabelecimento();latitude=coordenadaFormulario("est-lat",90);longitude=coordenadaFormulario("est-lng",180);}
        await ChurrasPlanAPI.criarEstabelecimento({nome:document.getElementById("est-nome").value.trim(),tipo:document.getElementById("est-tipo").value,endereco:document.getElementById("est-endereco").value.trim()||null,cidade:document.getElementById("est-cidade").value.trim()||null,estado:document.getElementById("est-estado").value.trim().toUpperCase()||null,cep:document.getElementById("est-cep").value.trim()||null,latitude,longitude,logradouro:null,numero:null,bairro:null,telefone:null,site:null,horario_funcionamento:null});
        e.target.reset();await carregarParceiro();mensagemParceiro("Estabelecimento cadastrado. A verificação administrativa é necessária antes da recomendação pública.");
    }catch(er){mensagemParceiro(er.message,"erro");}};
    document.getElementById("form-produto").onsubmit=async(e)=>{e.preventDefault();try{
        const produtoPaiId=Number(document.getElementById("prod-pai").value);
        if(!produtoPaiId) throw new Error("Selecione a categoria e o produto genérico.");
        await ChurrasPlanAPI.criarProdutoComercial({produto_pai_id:produtoPaiId,nome:document.getElementById("prod-nome").value.trim(),marca:document.getElementById("prod-marca").value.trim(),variante:document.getElementById("prod-variante").value.trim()||null,fabricante:null,ean:document.getElementById("prod-ean").value.trim()||null,sku:null,unidade_venda:document.getElementById("prod-venda").value.trim(),quantidade_embalagem:Number(document.getElementById("prod-qtd").value),unidade_embalagem:document.getElementById("prod-unidade").value.trim(),imagem_url:null,descricao:null});
        e.target.reset();await carregarParceiro();mensagemParceiro("Produto comercial cadastrado.");
    }catch(er){mensagemParceiro(er.message,"erro");}};
    document.getElementById("form-preco").onsubmit=async(e)=>{e.preventDefault();try{await ChurrasPlanAPI.cadastrarPrecoParceiro({produto_id:Number(document.getElementById("preco-prod").value),estabelecimento_id:Number(document.getElementById("preco-est").value),preco:Number(document.getElementById("preco-valor").value),preco_original:document.getElementById("preco-original").value===''?null:Number(document.getElementById("preco-original").value),inicio_validade:isoInput("preco-inicio"),fim_validade:isoInput("preco-fim"),estoque_status:document.getElementById("preco-estoque").value});e.target.reset();await carregarParceiro();mensagemParceiro("Preço cadastrado com sucesso.");}catch(er){mensagemParceiro(er.message,"erro");}};
});
