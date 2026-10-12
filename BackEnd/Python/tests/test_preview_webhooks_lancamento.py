from config import settings
from database.connection import get_db
from main import app
from models import Produto, ImportacaoCatalogo, TarefaOutbox
from services.outbox import processar_um
from tests.test_integracao_churrascos import client
from tests.test_fases_3_a_6 import cadastro_login
from tests.test_tenants_saas import _ativar
from tests.test_billing_usuario_stripe import stripe_pessoal_fake, postar_webhook


def test_catalogo_previa_nao_persiste_nem_consume_quota(client):
    _,h=cadastro_login(client,'preview@example.com');_ativar(client,h)
    pai=next(p for p in client.get('/api/produtos/genericos').json() if p['slug']=='agua')
    p={'chave_idempotencia':'preview-catalogo-001','csv_texto':f'sku;produto_pai_id;nome;marca;unidade_venda;quantidade_embalagem;unidade_embalagem\nTESTE;{pai["id"]};Água teste;Marca;garrafa;1.5;litro\n'}
    r=client.post('/api/parceiro/importacoes/catalogo?previa=true',json=p,headers=h)
    assert r.status_code==201 and r.json()['previa'] and r.json()['criados']==1,r.text
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.query(Produto).filter_by(sku='TESTE').count()==0
        assert db.query(ImportacaoCatalogo).count()==0
    assert client.post('/api/parceiro/importacoes/catalogo',json=p,headers=h).json()['criados']==1


def test_webhook_duravel_assinado_dedup_e_worker_reconcilia(client,stripe_pessoal_fake,monkeypatch):
    cadastro_login(client,'fila-billing@example.com');h={'X-CSRF-Token':client.cookies.get('churrasplan_csrf')}
    client.post('/api/billing/usuario/checkout',headers=h,json={'plano':'premium','periodicidade':'mensal','chave_idempotencia':'fila-checkout-001'})
    sessao=stripe_pessoal_fake['sessions']['cs_test_premium_1'];sessao['status']='complete';sessao['payment_status']='paid'
    monkeypatch.setattr(settings,'BILLING_WEBHOOK_ASYNC',True)
    obj={'id':'cs_test_premium_1','subscription':'sub_premium_1'}
    for _ in range(2):assert postar_webhook(client,'checkout.session.completed',obj,eid='evt_fila_test_001').json()['status']=='enfileirado'
    assert not client.get('/api/billing/usuario/assinatura').json()['beneficios_ativos']
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.query(TarefaOutbox).filter_by(tipo='billing_webhook').count()==1
        # Primeiro processa e-mail fictício de cadastro com transporte simulado.
        while processar_um(db,enviar=lambda *args:True):pass
    assert client.get('/api/billing/usuario/assinatura').json()['beneficios_ativos']
