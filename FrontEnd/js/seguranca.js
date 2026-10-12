let mfaAtivo = false;
function mfaMensagem(texto) { document.getElementById('saas-msg').textContent = texto; }
function mfaDestino() { return ChurrasPlanAuth.destinoSeguro(new URLSearchParams(location.search).get('next'), 'minha-conta.html'); }
async function carregarMFA() {
    const status = await requisitar('/api/auth/mfa/status'); mfaAtivo = status.ativo;
    document.getElementById('mfa-status').textContent = status.ativo ? `Proteção ativa. ${status.codigos_restantes} códigos de recuperação disponíveis.` : (status.obrigatorio ? 'Ative o segundo fator para acessar as funções administrativas.' : 'Ative a proteção para sua conta.');
    document.getElementById('mfa-configurar').hidden = status.ativo;
    document.getElementById('mfa-revogar').hidden = !status.ativo;
}
document.addEventListener('DOMContentLoaded', async () => {
    try { await carregarMFA(); } catch (erro) { if (erro.status === 401) location.assign(ChurrasPlanAuth.urlLogin('seguranca.html')); else mfaMensagem(erro.message); }
    document.getElementById('mfa-configurar').onsubmit = async e => {
        e.preventDefault(); const b=e.currentTarget.querySelector('button'); b.disabled=true;
        try { const r=await requisitar('/api/auth/mfa/configurar',{method:'POST',body:JSON.stringify({senha:document.getElementById('mfa-senha').value})}); document.getElementById('mfa-chave').textContent=r.segredo; document.getElementById('mfa-segredo').hidden=false; document.getElementById('mfa-senha').value=''; mfaMensagem(r.mensagem); } catch(erro){mfaMensagem(erro.message);} finally{b.disabled=false;}
    };
    document.getElementById('mfa-confirmar').onsubmit = async e => {
        e.preventDefault(); const b=e.currentTarget.querySelector('button'); b.disabled=true;
        try { const r=await requisitar(`/api/auth/mfa/${mfaAtivo?'verificar':'ativar'}`,{method:'POST',body:JSON.stringify({codigo:document.getElementById('mfa-codigo').value.trim()})}); document.getElementById('mfa-codigo').value=''; document.getElementById('mfa-segredo').hidden=true; document.getElementById('mfa-chave').textContent=''; if(r.codigos_recuperacao){document.getElementById('mfa-codigos').textContent=r.codigos_recuperacao.join('\n');document.getElementById('mfa-backup').hidden=false;document.getElementById('mfa-confirmar').hidden=true;await carregarMFA();}else location.assign(mfaDestino()); } catch(erro){mfaMensagem(erro.message);}finally{b.disabled=false;}
    };
    document.getElementById('mfa-continuar').onclick=()=>location.assign(mfaDestino());
    document.getElementById('mfa-revogar').onsubmit=async e=>{e.preventDefault();try{const r=await requisitar('/api/auth/mfa/substituir',{method:'POST',body:JSON.stringify({senha:document.getElementById('revogar-senha').value,codigo:document.getElementById('revogar-codigo').value.trim()})});mfaAtivo=false;document.getElementById('mfa-chave').textContent=r.segredo;document.getElementById('mfa-segredo').hidden=false;document.getElementById('mfa-revogar').hidden=true;document.getElementById('revogar-senha').value='';document.getElementById('revogar-codigo').value='';mfaMensagem(r.mensagem);}catch(erro){mfaMensagem(erro.message);}};
});
