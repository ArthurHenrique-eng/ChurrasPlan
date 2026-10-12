import base64
import hashlib
from datetime import timedelta
import pyotp
import pytest
from sqlalchemy import text
from config import settings
from database.connection import get_db
from main import app
from models import Usuario, CredencialMFA, RecuperacaoMFA, SessaoUsuario, TarefaOutbox
from services.auth import hash_senha, agora
from services.outbox import enfileirar_email, processar_um
from services.criptografia import decifrar
from tests.test_integracao_churrascos import client
from tests.test_fases_3_a_6 import cadastro_login


def db_atual(): return next(app.dependency_overrides[get_db]())
def csrf(client): return {'X-CSRF-Token':client.cookies.get('churrasplan_csrf')}


def test_argon2_migra_hash_legado_no_login(client):
    salt=b'0123456789abcdef'
    digest=hashlib.pbkdf2_hmac('sha256',b'SenhaLegada123',salt,600000)
    legado='pbkdf2_sha256$600000$'+base64.urlsafe_b64encode(salt).decode()+'$'+base64.urlsafe_b64encode(digest).decode()
    with db_atual() as db:
        db.add(Usuario(nome='Legado',email='legado@example.com',senha_hash=legado));db.commit()
    assert client.post('/api/auth/login',json={'email':'legado@example.com','senha':'SenhaLegada123'}).status_code==200
    with db_atual() as db: assert db.query(Usuario).filter_by(email='legado@example.com').one().senha_hash.startswith('$argon2id$')
    assert client.post('/api/auth/login',json={'email':'legado@example.com','senha':'Errada123456'}).status_code==401


def test_admin_exige_mfa_e_recuperacao_nao_pode_ser_reutilizada(client,monkeypatch):
    monkeypatch.setattr(settings,'MFA_REQUIRED_ADMIN',True)
    with db_atual() as db:
        db.add(Usuario(nome='Admin MFA',email='mfa@example.com',senha_hash=hash_senha('SenhaMfaTeste123'),papel='admin'));db.commit()
    assert client.post('/api/auth/login',json={'email':'mfa@example.com','senha':'SenhaMfaTeste123'}).status_code==200
    assert client.get('/api/auth/me').status_code==200
    assert client.get('/api/admin/dashboard').json()['detail']['codigo']=='MFA_NECESSARIO'
    assert client.post('/api/auth/mfa/configurar',json={'senha':'SenhaMfaTeste123'}).status_code==403
    config=client.post('/api/auth/mfa/configurar',json={'senha':'SenhaMfaTeste123'},headers=csrf(client));assert config.status_code==200,config.text
    segredo=config.json()['segredo']
    ativacao=client.post('/api/auth/mfa/ativar',json={'codigo':pyotp.TOTP(segredo).now()},headers=csrf(client));assert ativacao.status_code==200,ativacao.text
    codigos=ativacao.json()['codigos_recuperacao'];assert len(codigos)==10
    with db_atual() as db:
        credencial=db.query(CredencialMFA).one();assert segredo not in credencial.segredo_cifrado;assert decifrar(credencial.segredo_cifrado)==segredo
        assert all(c.codigo_hash not in codigos for c in db.query(RecuperacaoMFA))
    assert client.get('/api/admin/dashboard').status_code==200
    assert client.post('/api/auth/mfa/configurar',json={'senha':'SenhaMfaTeste123'},headers=csrf(client)).status_code==409
    client.post('/api/auth/logout',headers=csrf(client))
    client.post('/api/auth/login',json={'email':'mfa@example.com','senha':'SenhaMfaTeste123'})
    assert client.get('/api/admin/dashboard').status_code==403
    assert client.post('/api/auth/mfa/verificar',json={'codigo':codigos[0]},headers=csrf(client)).status_code==200
    assert client.post('/api/auth/mfa/verificar',json={'codigo':codigos[0]},headers=csrf(client)).status_code==401
    assert client.get('/api/auth/mfa/status').json()['codigos_restantes']==9
    assert client.post('/api/auth/mfa/revogar',json={'senha':'SenhaMfaTeste123','codigo':codigos[1]},headers=csrf(client)).status_code==409


def test_totp_replay_na_ativacao_e_segundo_login(client):
    cadastro_login(client,'totp@example.com');h=csrf(client)
    segredo=client.post('/api/auth/mfa/configurar',json={'senha':'SenhaForte123'},headers=h)
    # helper existente usa senha definida em cadastro_login.
    if segredo.status_code==401:
        with db_atual() as db:
            u=db.query(Usuario).filter_by(email='totp@example.com').one();u.senha_hash=hash_senha('SenhaForte123');db.commit()
        segredo=client.post('/api/auth/mfa/configurar',json={'senha':'SenhaForte123'},headers=h)
    codigo=pyotp.TOTP(segredo.json()['segredo']).now()
    assert client.post('/api/auth/mfa/ativar',json={'codigo':codigo},headers=h).status_code==200
    assert client.post('/api/auth/mfa/verificar',json={'codigo':codigo},headers=h).status_code==401


def test_limite_global_nao_depende_de_user_agent(client,monkeypatch):
    monkeypatch.setattr(settings,'RATE_LIMIT_READ_PER_MINUTE',2)
    monkeypatch.setattr(settings,'SECURITY_PEPPER','isolated-health-rate-test-pepper-123456789')
    for ua in ['primeiro','segundo']:
        assert client.get('/api/health',headers={'User-Agent':ua}).status_code==200
    resposta=client.get('/api/health',headers={'User-Agent':'terceiro'})
    assert resposta.status_code==429 and int(resposta.headers['retry-after'])>0


def test_body_chunked_e_origem_maliciosa(client,monkeypatch):
    monkeypatch.setattr(settings,'MAX_REQUEST_BODY_BYTES',20)
    r=client.post('/api/auth/login',content=iter([b'x'*15,b'y'*15]),headers={'Content-Type':'application/json'})
    assert r.status_code==413,r.text
    r=client.post('/api/auth/login',json={},headers={'Origin':'https://malicioso.example'})
    assert r.status_code==403


def test_request_id_sanitizado_e_api_privada_sem_cache(client):
    r=client.get('/api/health',headers={'X-Request-ID':'SEGREDO?token=nao-logar'})
    assert '?' not in r.headers['x-request-id']
    assert r.headers['cache-control'].startswith('no-store')


def test_outbox_dedup_retry_e_payload_purgado(client):
    with db_atual() as db:
        enfileirar_email(db,'ficticio@example.com','Teste','corpo de teste')
        enfileirar_email(db,'ficticio@example.com','Teste','corpo de teste');db.commit()
        assert db.query(TarefaOutbox).count()==1
        assert 'ficticio' not in db.query(TarefaOutbox).one().payload_cifrado
        assert processar_um(db,enviar=lambda *args:False)
        t=db.query(TarefaOutbox).one();assert t.status=='pendente' and t.tentativas==1 and t.erro_tipo=='RuntimeError'
        assert not processar_um(db,enviar=lambda *args:True)
        t.disponivel_em=agora()-timedelta(seconds=1);db.commit()
        assert processar_um(db,enviar=lambda *args:True)
        db.expire_all();t=db.query(TarefaOutbox).one();assert t.status=='concluido' and decifrar(t.payload_cifrado)=='{}'
        assert not processar_um(db,enviar=lambda *args:True)


def test_outbox_recupera_lease_e_chega_a_dead_letter(client,monkeypatch):
    monkeypatch.setattr(settings,'OUTBOX_MAX_ATTEMPTS',1)
    with db_atual() as db:
        enfileirar_email(db,'ficticio@example.com','Teste','corpo')
        t=db.query(TarefaOutbox).one();t.status='processando';t.lease_ate=agora()-timedelta(minutes=1);db.commit()
        assert processar_um(db,enviar=lambda *args:False)
        db.expire_all();assert db.query(TarefaOutbox).one().status=='falhou'
        assert not processar_um(db,enviar=lambda *args:True)


def test_cadastro_enfileira_email_na_mesma_transacao(client):
    cadastro_login(client,'fila@example.com')
    with db_atual() as db:
        assert db.query(TarefaOutbox).filter_by(tipo='email',status='pendente').count()==1
    assert client.get('/api/admin/operacao/tarefas').status_code==403


def test_geoapify_timeout_retries_circuito_e_sem_chave_nos_logs(monkeypatch,caplog):
    from services import geoapify as geo
    import urllib.error
    geo._cache.clear();geo._consumo.clear();geo._falhas=0;geo._aberto_ate=0
    calls=[]
    def fail(*args,**kwargs):calls.append(1);raise urllib.error.URLError('chave-ultrassecreta')
    monkeypatch.setattr(geo.urllib.request,'urlopen',fail)
    monkeypatch.setattr(geo.time,'sleep',lambda _:None)
    for _ in range(4):assert geo._get_json('https://api.geoapify.com/v2/places?apiKey=chave-ultrassecreta')=={}
    assert len(calls)==6
    assert 'chave-ultrassecreta' not in caplog.text
    geo._falhas=0;geo._aberto_ate=0


def test_geoapify_coordenadas_invalidas_nao_chama_provedor(monkeypatch):
    from services import geoapify as geo
    monkeypatch.setattr(settings,'GEOAPIFY_ENABLED',True);monkeypatch.setattr(settings,'GEOAPIFY_SERVER_API_KEY','chave-de-teste')
    monkeypatch.setattr(geo,'_get_json',lambda _:pytest.fail('Não deve chamar provedor'))
    assert geo.buscar_proximos(float('nan'),-44)==[]
    assert geo.buscar_proximos(-19959383,-44011870)==[]


def test_telemetria_rejeita_texto_livre_e_segredos(client):
    assert client.post('/api/telemetria/frontend',json={'codigo':'falha_api','pagina':'home'}).status_code==204
    assert client.post('/api/telemetria/frontend',json={'codigo':'falha_api','pagina':'home','email':'privado@example.com'}).status_code==422
    assert client.post('/api/telemetria/frontend',json={'codigo':'token=secreto','pagina':'home'}).status_code==422


def test_stripe_client_timeout_rak_e_idempotencia_sem_request_real(monkeypatch):
    from services import billing
    monkeypatch.setattr(settings,'BILLING_ENABLED',True)
    monkeypatch.setattr(settings,'STRIPE_SECRET_KEY','rk_test_example')
    monkeypatch.setattr(settings,'STRIPE_WEBHOOK_SECRET','whsec_example')
    calls=[]
    class Cliente:
        def __init__(self,key,**kwargs):
            assert key=='rk_test_example' and kwargs['max_network_retries']==1
        def raw_request(self,method,path,**kwargs):
            calls.append((method,path,kwargs));return {'id':'cs_test_example'}
    monkeypatch.setattr(billing.stripe,'StripeClient',Cliente)
    assert billing.stripe_request('POST','/v1/checkout/sessions',{},idempotency='test-same-key')['id']=='cs_test_example'
    billing.stripe_request('POST','/v1/checkout/sessions',{},idempotency='test-same-key')
    assert calls[0][2]['integration_identifier']==calls[1][2]['integration_identifier']
    assert calls[0][2]['idempotency_key']=='test-same-key'
