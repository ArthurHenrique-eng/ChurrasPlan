document.addEventListener('DOMContentLoaded',()=>{
    const alvo=document.querySelector('.account-shell');if(!alvo)return;
    const sec=document.createElement('section');sec.className='account-section saas-card retention-section';
    sec.innerHTML='<div class="cartao__titulo"><span class="section-icon" data-icon="clock"></span><h2>Use seu próximo churrasco como ponto de partida</h2></div>'
        +'<nav class="retention-links" aria-label="Mais recursos da conta"><a href="seguranca.html">Segurança da conta</a><a href="profissional.html">Clientes e propostas</a><a href="parceiros.html">Conhecer ChurrasPlan Parceiros</a></nav>'
        +'<div class="retention-grid">'
        +'<div class="retention-block"><h3>Indicar o ChurrasPlan</h3><p class="texto-suave">Crie um link para compartilhar. Nenhuma identidade de convidado é exibida.</p><button class="btn btn--secondary" id="indicacao-criar" type="button">Criar meu link de indicação</button><p id="indicacao-aviso" role="status"></p></div>'
        +'<div class="retention-block"><form id="lembrete-form"><h3>Solicitar um lembrete por e-mail</h3><div class="grade-campos grade-campos--2"><label class="campo">Planejamento<select id="lembrete-evento" required></select></label><label class="campo">Data e horário<input id="lembrete-quando" type="datetime-local" required></label></div><button class="btn btn--secondary" type="submit">Agendar lembrete</button></form><div id="lembretes-lista"></div></div>'
        +'</div>';
    // Fica antes de "Privacidade e dados", que encerra a página.
    alvo.insertBefore(sec, alvo.querySelector(':scope > .privacy-center'));
    window.ChurrasIcons?.hydrate(sec);
    const msg=document.getElementById('indicacao-aviso');
    document.getElementById('indicacao-criar').onclick=async e=>{if(!ChurrasPlanAnalytics.permitido()){msg.textContent='Para medir indicações, permita métricas nas preferências de cookies.';ChurrasPlanAnalytics.abrirEscolha();return;}e.currentTarget.disabled=true;try{const r=await requisitar('/api/growth/indicacoes',{method:'POST',body:JSON.stringify({consentimento:true})});msg.textContent=`${r.link} · ${r.cadastros_atribuidos} cadastro(s) atribuído(s). Nenhuma identidade de convidado é exibida.`;}catch(x){msg.textContent=x.message;}finally{e.currentTarget.disabled=false;}};
    async function carregar(){const [eventos,lembretes]=await Promise.all([ChurrasPlanAPI.meusChurrascos(),requisitar('/api/retencao/lembretes')]);document.getElementById('lembrete-evento').innerHTML=eventos.map(c=>`<option value="${c.id}">${escaparHTML(c.nome||'Churrasco')}</option>`).join('');document.getElementById('lembretes-lista').innerHTML=lembretes.map(r=>`<p>Lembrete: ${new Date(r.quando).toLocaleString('pt-BR')} <button type="button" data-cancelar-lembrete="${r.id}">Cancelar</button></p>`).join('');document.querySelectorAll('[data-cancelar-lembrete]').forEach(b=>b.onclick=async()=>{try{await requisitar(`/api/retencao/lembretes/${b.dataset.cancelarLembrete}`,{method:'DELETE'});await carregar();}catch(e){msg.textContent=e.message;}});}
    carregar().catch(()=>{});
    document.getElementById('lembrete-form').onsubmit=async e=>{e.preventDefault();try{await requisitar('/api/retencao/lembretes',{method:'POST',body:JSON.stringify({churrasco_id:Number(document.getElementById('lembrete-evento').value),quando:new Date(document.getElementById('lembrete-quando').value).toISOString()})});msg.textContent='Lembrete agendado. Você pode cancelá-lo aqui.';await carregar();}catch(x){msg.textContent=x.message;}};
});
