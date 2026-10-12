import pytest
from utils.validators import validar_ean
from tests.test_integracao_churrascos import client
from tests.test_fases_3_a_6 import cadastro_login
from tests.test_tenants_saas import _ativar


@pytest.mark.parametrize('codigo',['4006381333931','96385074','036000291452'])
def test_gtin_digito_verificador(codigo):assert validar_ean(codigo)==codigo


@pytest.mark.parametrize('codigo',['4006381333932','1234567890123','ABCD1234','123456789'])
def test_gtin_invalido(codigo):
    with pytest.raises(ValueError):validar_ean(codigo)


def test_ean_compartilhavel_entre_empresas_sem_vazar_catalogo(client):
    _,h=cadastro_login(client,'ean1@example.com');_ativar(client,h)
    pai=next(p for p in client.get('/api/produtos/genericos').json() if p['slug']=='agua')
    p={'produto_pai_id':pai['id'],'nome':'Água teste','marca':'Marca teste','ean':'4006381333931','unidade_venda':'garrafa','quantidade_embalagem':1.5,'unidade_embalagem':'litro'}
    a=client.post('/api/parceiro/produtos',json=p,headers=h);assert a.status_code==201,a.text
    assert client.post('/api/parceiro/produtos',json=p,headers=h).status_code==409
    client.post('/api/auth/logout',headers=h)
    _,h=cadastro_login(client,'ean2@example.com');_ativar(client,h)
    b=client.post('/api/parceiro/produtos',json=p,headers=h);assert b.status_code==201,b.text
    assert a.json()['id']!=b.json()['id']
    assert {x['id'] for x in client.get('/api/parceiro/produtos').json()}=={b.json()['id']}
