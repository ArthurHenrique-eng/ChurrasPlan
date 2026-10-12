from datetime import UTC, datetime, timedelta
import pytest
from config import settings
from database.connection import get_db
from main import app
from models import Usuario, LeadComercial, EventoProduto, IndicacaoUsuario, AtribuicaoCadastro, TarefaOutbox
from services.auth import hash_senha
from tests.test_integracao_churrascos import client,payload
from tests.test_fases_3_a_6 import cadastro_login


def db_atual():return next(app.dependency_overrides[get_db]())
def csrf(c):return {'X-CSRF-Token':c.cookies.get('churrasplan_csrf')}

def lead(**alteracoes):
    dados=dict(nome='Pessoa de teste',email='lead@example.com',empresa='Mercado teste',cidade='Belo Horizonte',tipo_estabelecimento='mercado',ciente_privacidade=True)
    dados.update(alteracoes);return dados


def test_lead_minimo_consentimento_opcional_dedup_e_honeypot(client):
    assert client.post('/api/growth/leads',json=lead()).status_code==202
    assert client.post('/api/growth/leads',json=lead(marketing=True)).status_code==202
    assert client.post('/api/growth/leads',json=lead(email='bot@example.com',site='spam')).status_code==202
    with db_atual() as db:
        l=db.query(LeadComercial).one();assert not l.marketing_concedido and len(l.descadastro_hash)==64
        assert db.query(EventoProduto).filter_by(evento='lead_criado').count()==1
    assert client.get('/api/admin/growth/leads').status_code==401
    assert client.post('/api/growth/leads',json=lead(ciente_privacidade=False)).status_code==422
    assert client.post('/api/growth/leads',json=lead(email='invalido')).status_code==422
    assert client.post('/api/growth/leads',json=lead(utm_source='email@example.com')).status_code==422


def test_analytics_consentimento_catalogo_dedup_sem_pii(client):
    p={'evento':'landing_visualizada','sessao':'sessaoanonima00000000','consentimento':True,'origem':'home'}
    assert client.post('/api/growth/eventos',json=p).status_code==204
    assert client.post('/api/growth/eventos',json=p).status_code==204
    with db_atual() as db:
        e=db.query(EventoProduto).filter_by(evento='landing_visualizada').one();assert e.propriedades=={'origem':'home','segmento':'b2c'}
        assert p['sessao'] not in e.dedup_hash
    assert client.post('/api/growth/eventos',json={**p,'consentimento':False}).status_code==422
    assert client.post('/api/growth/eventos',json={**p,'evento':'assinatura_paga'}).status_code==422


def test_indicacao_atribuida_somente_com_consentimento_e_sem_identidade(client):
    cadastro_login(client,'indica@example.com')
    r=client.post('/api/growth/indicacoes',json={'consentimento':True},headers=csrf(client));assert r.status_code==200
    codigo=r.json()['link'].split('ref=')[1]
    client.post('/api/auth/logout',headers=csrf(client))
    r=client.post('/api/auth/register',json={'nome':'Pessoa indicada','email':'indicada@example.com','senha':'SenhaForte123','aceite_termos':True,'aceite_privacidade':True,'referral_codigo':codigo,'aceite_analytics':True})
    assert r.status_code==201,r.text
    with db_atual() as db:assert db.query(AtribuicaoCadastro).count()==1
    assert client.post('/api/growth/indicacoes',json={'consentimento':False},headers=csrf(client)).status_code==422


def test_crm_conversao_exige_organizacao_e_audita(client):
    client.post('/api/growth/leads',json=lead())
    with db_atual() as db:
        db.add(Usuario(nome='Admin',email='crm-admin@example.com',senha_hash=hash_senha('SenhaAdmin123'),papel='admin'));db.commit()
    client.post('/api/auth/login',json={'email':'crm-admin@example.com','senha':'SenhaAdmin123'})
    registros=client.get('/api/admin/growth/leads').json();ident=registros[0]['id']
    assert client.patch(f'/api/admin/growth/leads/{ident}',json={'status':'convertido'},headers=csrf(client)).status_code==422
    r=client.patch(f'/api/admin/growth/leads/{ident}',json={'status':'piloto','nota':'Entrevista agendada pelo lead'},headers=csrf(client));assert r.status_code==200
    assert any(a['tipo']=='piloto' for a in r.json()['atividades'])
    dash=client.get('/api/admin/growth/dashboard');assert dash.status_code==200,dash.text
    assert dash.json()['mrr_real'] is None and dash.json()['cac_real'] is None
    assert client.post('/api/admin/growth/custos',json={'competencia':'2026-10','categoria':'infraestrutura','valor':'50.00'},headers=csrf(client)).status_code==201


def test_profissional_isolamento_cotas_e_proposta_com_snapshot(client):
    cadastro_login(client,'prof@example.com');h=csrf(client)
    ids=[]
    for n in range(3):
        r=client.post('/api/profissional/clientes',json={'nome':f'Cliente {n}'},headers=h);assert r.status_code==201,r.text;ids.append(r.json()['id'])
    assert client.post('/api/profissional/clientes',json={'nome':'Quarto'},headers=h).status_code==409
    evento=client.post('/api/churrascos',json=payload(chave_cliente='proposta-evento-0001'),headers=h);assert evento.status_code==201
    dados={'chave':'proposta-unica-001','cliente_id':ids[0],'churrasco_id':evento.json()['id'],'titulo':'Churrasco empresa','custos_adicionais':'10.00','preco_proposto':'600.00'}
    r=client.post('/api/profissional/propostas',json=dados,headers=h);assert r.status_code==201,r.text
    ident=r.json()['id'];assert float(r.json()['custo_estimado'])==evento.json()['custo_total_estimado']+10
    assert client.post('/api/profissional/propostas',json=dados,headers=h).json()['id']==ident
    assert client.post('/api/profissional/propostas',json={**dados,'preco_proposto':'500.00'},headers=h).status_code==409
    assert client.get(f'/api/profissional/propostas/{ident}/pdf').status_code==403
    client.post('/api/auth/logout',headers=h);cadastro_login(client,'outro-prof@example.com')
    assert client.get('/api/profissional/clientes').json()==[]
    assert client.put(f'/api/profissional/clientes/{ids[0]}',json={'nome':'Invadido'},headers=csrf(client)).status_code==404
    assert client.patch(f'/api/profissional/propostas/{ident}',json={'status':'aceita'},headers=csrf(client)).status_code==404


def test_lembrete_exige_titularidade_fuso_e_cancelamento(client):
    cadastro_login(client,'lembrete@example.com');h=csrf(client)
    c=client.post('/api/churrascos',json=payload(chave_cliente='lembrete-evento-0001'),headers=h).json()
    quando=(datetime.now(UTC)+timedelta(days=1)).isoformat()
    r=client.post('/api/retencao/lembretes',json={'churrasco_id':c['id'],'quando':quando},headers=h);assert r.status_code==201,r.text
    ident=r.json()['id']
    assert client.post('/api/retencao/lembretes',json={'churrasco_id':c['id'],'quando':quando},headers=h).json()['id']==ident
    assert client.post('/api/retencao/lembretes',json={'churrasco_id':c['id'],'quando':'2027-01-01T10:00:00'},headers=h).status_code==422
    assert client.delete(f'/api/retencao/lembretes/{ident}',headers=h).status_code==204
    with db_atual() as db:assert db.query(TarefaOutbox).filter_by(status='cancelado').count()==1


def test_marketing_descadastro_funciona_e_formulario_nao_reinscreve(client):
    from services.auth import hash_token
    from routers.growth import token_descadastro
    client.post('/api/growth/leads',json=lead(marketing=True))
    with db_atual() as db:
        l=db.query(LeadComercial).filter_by(email='lead@example.com').one();token=token_descadastro(l.id)
        assert l.descadastro_hash==hash_token(token) and l.marketing_concedido
    assert client.post('/api/growth/marketing/descadastrar',json={'token':token}).status_code==200
    client.post('/api/growth/leads',json=lead(marketing=True))
    with db_atual() as db:assert not db.query(LeadComercial).filter_by(email='lead@example.com').one().marketing_concedido


def test_transferencia_propriedade_senha_escopo_e_permissoes(client):
    from fastapi.testclient import TestClient
    from models import OrganizacaoMembro
    from tests.test_tenants_saas import _ativar
    _,h=cadastro_login(client,'owner-transfer@example.com');oid=_ativar(client,h)
    with TestClient(app) as outro:
        resposta,hb=cadastro_login(outro,'new-owner@example.com');uid=resposta['usuario']['id']
        with db_atual() as db:
            db.add(OrganizacaoMembro(organizacao_id=oid,usuario_id=uid,papel='editor'));db.commit()
        body={'novo_usuario_id':uid,'senha':'Errada123456','confirmacao':'TRANSFERIR'}
        assert client.post('/api/parceiro/equipe/transferir-propriedade',json=body,headers=h).status_code==403
        body['senha']='SenhaForte123'
        r=client.post('/api/parceiro/equipe/transferir-propriedade',json=body,headers=h);assert r.status_code==200,r.text
        with db_atual() as db:
            alvo=db.query(OrganizacaoMembro).filter_by(organizacao_id=oid,usuario_id=uid).one();assert alvo.papel=='proprietario' and alvo.usuario.papel=='parceiro'
        assert client.get('/api/billing/assinatura').status_code==403
        assert outro.get('/api/billing/assinatura').status_code==200


def test_cenarios_sao_hipoteses_e_nao_criam_assinaturas(client):
    with db_atual() as db:
        db.add(Usuario(nome='Admin',email='cenario@example.com',senha_hash=hash_senha('SenhaAdmin123'),papel='admin'));db.commit()
    client.post('/api/auth/login',json={'email':'cenario@example.com','senha':'SenhaAdmin123'})
    p={'ticket_mensal':'50.00','custo_fixo_mensal':'100.00','custo_variavel_cliente':'5.00','clientes_conservador':10,'clientes_base':20,'clientes_otimista':30}
    r=client.post('/api/admin/growth/cenarios',json=p,headers=csrf(client));assert r.status_code==200
    assert float(r.json()['cenarios'][0]['mrr_hipotetico'])==500
    assert float(r.json()['cenarios'][0]['resultado_mensal_hipotetico'])==350
    assert client.get('/api/admin/growth/dashboard').json()['mrr_real'] is None


def test_owner_pode_encerrar_org_free_e_excluir_conta(client):
    from tests.test_tenants_saas import _ativar
    _,h=cadastro_login(client,'owner-close@example.com');_ativar(client,h)
    assert client.request('DELETE','/api/privacidade/minha-conta',json={'senha':'SenhaForte123','confirmacao':'EXCLUIR'},headers=h).status_code==409
    assert client.post('/api/parceiro/organizacao/encerrar',json={'senha':'Errada123456','confirmacao':'ENCERRAR'},headers=h).status_code==403
    assert client.post('/api/parceiro/organizacao/encerrar',json={'senha':'SenhaForte123','confirmacao':'ENCERRAR'},headers=h).status_code==200
    assert client.request('DELETE','/api/privacidade/minha-conta',json={'senha':'SenhaForte123','confirmacao':'EXCLUIR'},headers=h).status_code==200
