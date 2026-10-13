from datetime import timedelta
from models import Churrasco, EventoProduto, Usuario
from services.auth import agora, hash_senha
from services.analytics import registrar_produto
from services.analytics_dashboard import funis_produto, retencao_planejamentos
from tests.test_integracao_churrascos import client
from tests.test_growth_profissional_lancamento import db_atual


def evento(db, nome, contexto, minuto, tipo="sessao_dia"):
    registrar_produto(db, nome, contexto + ':' + nome, {"segmento": "b2c" if tipo == "sessao_dia" else "b2b"}, contexto=contexto, contexto_tipo=tipo)
    registro = db.query(EventoProduto).filter_by(evento=nome).order_by(EventoProduto.id.desc()).first()
    registro.criado_em = agora() - timedelta(minutes=minuto)
    db.flush()


def test_funil_ordem_abandono_dedup_e_entrada_direta(client):
    with db_atual() as db:
        for nome, minuto in [('landing_visualizada',10),('planejamento_iniciado',9),('planejamento_concluido',8),('resultado_visualizado',7)]:
            evento(db,nome,'sessao-a-dia',minuto)
        for nome, minuto in [('landing_visualizada',10),('planejamento_iniciado',9)]:evento(db,nome,'sessao-b-dia',minuto)
        evento(db,'planejamento_iniciado','entrada-direta',9)
        for nome, minuto in [('landing_visualizada',10),('planejamento_iniciado',9),('planejamento_concluido',7),('resultado_visualizado',8)]:
            evento(db,nome,'sessao-c-dia',minuto)
        registrar_produto(db,'landing_visualizada','sessao-a-dia:landing_visualizada',{},contexto='sessao-a-dia',contexto_tipo='sessao_dia')
        etapas=funis_produto(db,agora()-timedelta(days=1))['resultados']['planejamento_b2c']['etapas']
        assert [e['quantidade'] for e in etapas]==[3,3,2,1]
        assert [e['abandonos_observados'] for e in etapas]==[None,0,1,1]
        assert etapas[-1]['conversao_inicio_pct']==33.33


def test_contextos_diarios_e_legados_nao_sao_vinculados(client):
    with db_atual() as db:
        evento(db,'landing_visualizada','mesma-sessao-dia-1',10)
        evento(db,'planejamento_iniciado','mesma-sessao-dia-2',9)
        db.add(EventoProduto(evento='landing_visualizada',propriedades={},dedup_hash='evento-legado-sem-contexto'))
        db.flush()
        dados=funis_produto(db,agora()-timedelta(days=1))['resultados']['planejamento_b2c']['etapas']
        assert [e['quantidade'] for e in dados]==[1,0,0,0]
        e=db.query(EventoProduto).filter_by(evento='planejamento_iniciado').one()
        assert len(e.contexto_hash)==64 and e.contexto_hash!=e.dedup_hash
        assert 'mesma-sessao' not in e.contexto_hash


def test_funis_sao_admin_e_so_retornam_agregados(client):
    assert client.get('/api/admin/growth/dashboard').status_code==401
    with db_atual() as db:
        db.add(Usuario(nome='Admin',email='funis-admin@example.com',senha_hash=hash_senha('SenhaAdminTeste123'),papel='admin'))
        evento(db,'landing_visualizada','contexto-privado-123',10);db.commit()
    assert client.post('/api/auth/login',json={'email':'funis-admin@example.com','senha':'SenhaAdminTeste123'}).status_code==200
    r=client.get('/api/admin/growth/dashboard');assert r.status_code==200,r.text
    assert 'contexto-privado' not in r.text and 'contexto_hash' not in r.text
    assert r.json()['retencao_planejamentos']['retencao_pct'] is None
    assert r.json()['mrr_real'] is None


def test_retencao_usa_contas_distintas_janelas_e_base_correta(client):
    with db_atual() as db:
        pessoas=[Usuario(nome='Teste',email=f'retencao-{n}@example.com',senha_hash='fixture-sem-login') for n in range(3)]
        db.add_all(pessoas);db.flush()
        for pessoa,dias in [(pessoas[0],40),(pessoas[0],10),(pessoas[0],5),(pessoas[1],40),(pessoas[2],10)]:
            db.add(Churrasco(usuario_id=pessoa.id,tipo_evento='almoco',duracao_horas=4,perfil_consumo='normal',criado_em=agora()-timedelta(days=dias)))
        db.flush()
        dados=retencao_planejamentos(db,30)
        assert dados['base_periodo_anterior']==2 and dados['ativos_periodo_atual']==2
        assert dados['retornaram']==1 and dados['retencao_pct']==50
        assert dados['planejamentos_salvos_periodo']==3 and dados['planejamentos_por_usuario_ativo']==1.5


def test_funil_b2b_nao_mistura_organizacoes(client):
    with db_atual() as db:
        evento(db,'organizacao_criada','tenant-a',10,'organizacao')
        evento(db,'estabelecimento_enviado','tenant-b',9,'organizacao')
        evento(db,'estabelecimento_enviado','tenant-a',9,'organizacao')
        evento(db,'estabelecimento_aprovado','tenant-b',8,'organizacao')
        etapas=funis_produto(db,agora()-timedelta(days=1))['resultados']['ativacao_b2b']['etapas']
        assert [e['quantidade'] for e in etapas]==[1,1,0,0,0]
