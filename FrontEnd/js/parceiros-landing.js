document.addEventListener('DOMContentLoaded',()=>{
    document.getElementById('lead-form').onsubmit=async e=>{
        e.preventDefault();const form=e.currentTarget,b=form.querySelector('button[type=submit]');b.disabled=true;
        const payload=Object.fromEntries(new FormData(form));payload.ciente_privacidade=form.elements.ciente_privacidade.checked;payload.marketing=form.elements.marketing.checked;
        const query=new URLSearchParams(location.search);for(const key of ['utm_source','utm_medium','utm_campaign']){const v=query.get(key);if(v&&/^[A-Za-z0-9_-]{1,60}$/.test(v))payload[key]=v;}
        try{const r=await requisitar('/api/growth/leads',{method:'POST',body:JSON.stringify(payload)});document.getElementById('saas-msg').textContent=r.mensagem;form.reset();}catch(erro){document.getElementById('saas-msg').textContent=erro.message;}finally{b.disabled=false;}
    };
});
