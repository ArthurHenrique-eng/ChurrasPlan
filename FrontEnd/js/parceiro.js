let parceiroUsuario = null, parceiroEstabelecimentos = [], parceiroProdutos = [], genericos = [];
function isoInput(id) { const v = document.getElementById(id).value; return v ? new Date(v).toISOString() : null; }
function mensagemParceiro(t, tipo="sucesso") { mostrarMensagem(document.getElementById("parceiro-mensagem"), t, tipo); }
function coordenadaFormulario(id, limite) {
    const campo = document.getElementById(id), bruto = campo.value.trim();
    if (!bruto) return null;
    let valor = Number(bruto.replace(",", "."));
    if (!Number.isFinite(valor)) throw new Error("Informe uma coordenada válida.");
    if (Math.abs(valor) >= 1000000 && Math.abs(valor) <= limite * 1000000 && Number.isInteger(valor)) valor /= 1000000;
    if (Math.abs(valor) > limite) throw new Error(`Coordenada fora do intervalo permitido (-${limite} a ${limite}).`);
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
async function carregarParceiro() {
    const [dash, ests, prods, gens] = await Promise.all([ChurrasPlanAPI.dashboardParceiro(), ChurrasPlanAPI.estabelecimentosParceiro(), ChurrasPlanAPI.produtosParceiro(), ChurrasPlanAPI.listarProdutos({ tipo_produto:"generico" })]);
    parceiroEstabelecimentos=ests; parceiroProdutos=prods; genericos=gens;
    document.getElementById("parceiro-stats").innerHTML = `<div class="partner-stat"><strong>${dash.estabelecimentos}</strong><span>estabelecimentos</span></div><div class="partner-stat"><strong>${dash.estabelecimentos_verificados}</strong><span>verificados</span></div><div class="partner-stat"><strong>${dash.ofertas_cadastradas}</strong><span>ofertas cadastradas</span></div><div class="partner-stat"><strong>${dash.visualizacoes || 0}</strong><span>visualizações</span></div><div class="partner-stat"><strong>${dash.cliques || 0}</strong><span>cliques em rota</span></div>`;
    document.getElementById("parceiro-note").textContent = dash.mensagem_verificacao;
    document.getElementById("lista-estabelecimentos").innerHTML = ests.length ? ests.map(e=>`<div class="basket-row"><strong>${escaparHTML(e.nome)}</strong><br><small>${escaparHTML(e.cidade||e.endereco||e.tipo)} · ${e.parceiro_verificado?'verificado':'aguardando verificação'}</small></div>`).join('') : '<div class="empty-state">Cadastre seu primeiro estabelecimento.</div>';
    document.getElementById("lista-produtos").innerHTML = prods.length ? prods.map(p=>`<div class="basket-row"><strong>${escaparHTML([p.marca,p.nome].filter(Boolean).join(' — '))}</strong><br><small>${p.quantidade_embalagem||''} ${escaparHTML(p.unidade_embalagem||'')} · ${escaparHTML(p.ean||'sem EAN')}</small></div>`).join('') : '<div class="empty-state">Nenhum SKU comercial cadastrado.</div>';
    const optionsEst = '<option value="">Selecione...</option>'+ests.map(e=>`<option value="${e.id}">${escaparHTML(e.nome)}</option>`).join(''); document.getElementById("preco-est").innerHTML=optionsEst;
    document.getElementById("prod-pai").innerHTML='<option value="">Selecione...</option>'+gens.map(p=>`<option value="${p.id}">${escaparHTML(p.nome)}</option>`).join('');
    document.getElementById("preco-prod").innerHTML='<option value="">Selecione...</option>'+prods.map(p=>`<option value="${p.id}">${escaparHTML([p.marca,p.nome].filter(Boolean).join(' — '))}</option>`).join('');
}
document.addEventListener("DOMContentLoaded", async()=>{
    parceiroUsuario=await ChurrasPlanAuth.usuarioAtual().catch(()=>null); if(!parceiroUsuario){irPara(ChurrasPlanAuth.urlLogin("parceiro.html"));return;}
    const ativar=document.getElementById("ativar-parceiro"), conteudo=document.getElementById("parceiro-conteudo");
    if(!["parceiro","admin"].includes(parceiroUsuario.papel)){ativar.hidden=false;ativar.onclick=async()=>{ativar.disabled=true;try{await ChurrasPlanAPI.ativarParceiro();ChurrasPlanAuth.limparCache();location.reload();}catch(e){mensagemParceiro(e.message,"erro");ativar.disabled=false;}};return;}
    conteudo.hidden=false; try{await carregarParceiro();}catch(e){mensagemParceiro(e.message,"erro");}
    document.getElementById("est-localizar-endereco").onclick=async()=>{const b=document.getElementById("est-localizar-endereco");b.disabled=true;try{await localizarEnderecoEstabelecimento();mensagemParceiro("Endereço localizado e coordenadas preenchidas.");}catch(er){mensagemParceiro(er.message,"erro");}finally{b.disabled=false;}};
    document.getElementById("form-estabelecimento").onsubmit=async(e)=>{e.preventDefault();try{
        let latitude=coordenadaFormulario("est-lat",90), longitude=coordenadaFormulario("est-lng",180);
        if((latitude===null||longitude===null)&&document.getElementById("est-endereco").value.trim()){await localizarEnderecoEstabelecimento();latitude=coordenadaFormulario("est-lat",90);longitude=coordenadaFormulario("est-lng",180);}
        await ChurrasPlanAPI.criarEstabelecimento({nome:document.getElementById("est-nome").value.trim(),tipo:document.getElementById("est-tipo").value,endereco:document.getElementById("est-endereco").value.trim()||null,cidade:document.getElementById("est-cidade").value.trim()||null,estado:document.getElementById("est-estado").value.trim().toUpperCase()||null,cep:document.getElementById("est-cep").value.trim()||null,latitude,longitude,logradouro:null,numero:null,bairro:null,telefone:null,site:null,horario_funcionamento:null});
        e.target.reset();await carregarParceiro();mensagemParceiro("Estabelecimento cadastrado. A verificação administrativa é necessária antes da recomendação pública.");
    }catch(er){mensagemParceiro(er.message,"erro");}};
    document.getElementById("form-produto").onsubmit=async(e)=>{e.preventDefault();try{await ChurrasPlanAPI.criarProdutoComercial({produto_pai_id:Number(document.getElementById("prod-pai").value),nome:document.getElementById("prod-nome").value.trim(),marca:document.getElementById("prod-marca").value.trim(),variante:document.getElementById("prod-variante").value.trim()||null,fabricante:null,ean:document.getElementById("prod-ean").value.trim()||null,sku:null,unidade_venda:document.getElementById("prod-venda").value.trim(),quantidade_embalagem:Number(document.getElementById("prod-qtd").value),unidade_embalagem:document.getElementById("prod-unidade").value.trim(),imagem_url:null,descricao:null});e.target.reset();await carregarParceiro();mensagemParceiro("Produto comercial cadastrado.");}catch(er){mensagemParceiro(er.message,"erro");}};
    document.getElementById("form-preco").onsubmit=async(e)=>{e.preventDefault();try{await ChurrasPlanAPI.cadastrarPrecoParceiro({produto_id:Number(document.getElementById("preco-prod").value),estabelecimento_id:Number(document.getElementById("preco-est").value),preco:Number(document.getElementById("preco-valor").value),preco_original:document.getElementById("preco-original").value===''?null:Number(document.getElementById("preco-original").value),inicio_validade:isoInput("preco-inicio"),fim_validade:isoInput("preco-fim"),estoque_status:document.getElementById("preco-estoque").value});e.target.reset();await carregarParceiro();mensagemParceiro("Preço cadastrado com sucesso.");}catch(er){mensagemParceiro(er.message,"erro");}};
});
