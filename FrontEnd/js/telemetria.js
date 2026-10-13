/** Sem mensagens, stacks, URLs, nomes ou corpo de requisição. */
const ChurrasPlanTelemetria=(()=>{
    let enviados=0;
    function registrar(codigo){
        if(enviados>=3||typeof API_BASE_URL==='undefined')return;
        enviados++;
        const mapa={'index.html':'home','planejamento.html':'planejamento','resultado.html':'resultado','minha-conta.html':'conta','parceiro.html':'parceiro'};
        const pagina=mapa[location.pathname.split('/').pop()]||'outro';
        fetch(`${API_BASE_URL}/api/telemetria/frontend`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({codigo,pagina}),keepalive:true}).catch(()=>{});
    }
    window.addEventListener('error',()=>registrar('erro_js'));
    window.addEventListener('unhandledrejection',()=>registrar('rejeicao_js'));
    return {registrar};
})();
