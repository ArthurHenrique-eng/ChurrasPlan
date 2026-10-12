/** Métricas opcionais: nenhum ID é criado antes do consentimento. */
const ChurrasPlanAnalytics=(()=>{
    let estado='essenciais';
    try{estado=localStorage.getItem('churrasplan_analytics')||'pendente';}catch{/* Sem storage: somente essenciais. */}
    function permitido(){return estado==='permitido';}
    function registrar(evento,origem='direto'){
        if(!permitido()||typeof API_BASE_URL==='undefined')return;
        try{let sessao=sessionStorage.getItem('churrasplan_analytics_sessao');if(!sessao){sessao=crypto.randomUUID();sessionStorage.setItem('churrasplan_analytics_sessao',sessao);}fetch(`${API_BASE_URL}/api/growth/eventos`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({evento,origem,sessao,consentimento:true}),keepalive:true}).catch(()=>{});}catch{/* Métricas nunca bloqueiam o produto. */}
    }
    function escolher(valor){estado=valor;try{localStorage.setItem('churrasplan_analytics',valor);if(valor!=='permitido'){sessionStorage.removeItem('churrasplan_analytics_sessao');sessionStorage.removeItem('churrasplan_referral');}}catch{}document.getElementById('analytics-choice')?.remove();if(permitido())pagina();}
    function pagina(){const nome=location.pathname.split('/').pop()||'index.html',ref=new URLSearchParams(location.search).get('ref');if(permitido()&&ref&&/^[A-Za-z0-9_-]{20,48}$/.test(ref)){try{sessionStorage.setItem('churrasplan_referral',ref);}catch{}}
        const mapa={'index.html':['landing_visualizada','home'],'planejamento.html':['planejamento_iniciado','planejamento'],'resultado.html':['resultado_visualizado','resultado'],'convite.html':['landing_visualizada','convite'],'parceiros.html':['landing_visualizada','parceiros'],'onde-comprar.html':['onde_comprar_acessado','onde_comprar']};if(mapa[nome])registrar(...mapa[nome]);
    }
    function abrirEscolha(){if(document.getElementById('analytics-choice'))return;const box=document.createElement('aside');box.id='analytics-choice';box.className='analytics-choice';box.setAttribute('aria-label','Preferências de métricas');const texto=document.createElement('p');texto.textContent='Podemos contar visitas e etapas do planejamento para melhorar o ChurrasPlan? É opcional e não coletamos nomes, e-mails ou localização nessas métricas.';box.append(texto);for(const [label,v]of[['Permitir métricas','permitido'],['Somente essenciais','essenciais']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=()=>escolher(v);box.append(b);}(document.querySelector('main') || document.body).prepend(box);}
    document.addEventListener('DOMContentLoaded',()=>{if(estado==='pendente')abrirEscolha();else pagina();
        if(typeof ChurrasPlanAPI!=='undefined'){for(const [nome,evento,origem]of[['criarChurrasco','planejamento_concluido','planejamento'],['criarConvite','convite_compartilhado','convite']]){const original=ChurrasPlanAPI[nome];if(original)ChurrasPlanAPI[nome]=async(...args)=>{const r=await original(...args);registrar(evento,origem);return r;};}}
        if(typeof ChurrasPlanAPI!=='undefined'&&ChurrasPlanAPI.registrarInteracoesEstabelecimentos){const original=ChurrasPlanAPI.registrarInteracoesEstabelecimentos;ChurrasPlanAPI.registrarInteracoesEstabelecimentos=async(...args)=>{const r=await original(...args);if(args[1]?.length)registrar(args[0]==='clique'?'parceiro_clicado':'parceiro_visualizado','onde_comprar');return r;};}
    });
    return {permitido,registrar,abrirEscolha,escolher};
})();

document.addEventListener('DOMContentLoaded',()=>{document.getElementById('cookies-preferencias')?.addEventListener('click',ChurrasPlanAnalytics.abrirEscolha);});
