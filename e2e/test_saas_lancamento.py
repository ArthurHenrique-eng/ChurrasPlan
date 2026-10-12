import uuid
import pyotp
from playwright.sync_api import expect
from test_churrasplan_e2e import url


def essenciais(page):
    botao=page.get_by_role('button',name='Somente essenciais',exact=True)
    if botao.count():botao.click()


def registrar_pela_interface(page):
    email='e2e-saas-'+uuid.uuid4().hex[:10]+'@example.com'
    page.goto(url('cadastro.html'),wait_until='domcontentloaded');essenciais(page)
    page.locator('#auth-nome').fill('Teste SaaS')
    page.locator('#auth-email').fill(email)
    page.locator('#auth-senha').fill('SenhaSaasTeste123')
    page.locator('#aceite-termos').check()
    page.locator('#aceite-privacidade').check()
    page.locator('#auth-form button[type=submit]').click()
    page.wait_for_url('**/minha-conta.html',timeout=15000)
    expect(page.locator('#conta-saudacao')).to_contain_text('Teste SaaS')
    return email


def test_landing_parceiros_mobile_e_interesse_real(page):
    page.set_viewport_size({'width':390,'height':844})
    page.goto(url('parceiros.html'),wait_until='domcontentloaded');essenciais(page)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    form=page.locator('#lead-form')
    form.locator('[name=nome]').fill('Pessoa de teste')
    form.locator('[name=email]').fill('e2e-lead-'+uuid.uuid4().hex[:10]+'@example.com')
    form.locator('[name=empresa]').fill('Mercado de teste E2E')
    form.locator('[name=cidade]').fill('Belo Horizonte')
    form.locator('[name=ciente_privacidade]').check()
    form.get_by_role('button',name='Registrar interesse').click()
    expect(page.locator('#saas-msg')).to_contain_text('Interesse recebido')


def test_mfa_configuracao_codigo_e_recuperacao_na_interface(page):
    registrar_pela_interface(page)
    page.goto(url('seguranca.html'),wait_until='domcontentloaded');essenciais(page)
    page.locator('#mfa-senha').fill('SenhaSaasTeste123')
    page.get_by_role('button',name='Cadastrar autenticador').click()
    expect(page.locator('#mfa-segredo')).to_be_visible()
    segredo=page.locator('#mfa-chave').inner_text()
    page.locator('#mfa-codigo').fill(pyotp.TOTP(segredo).now())
    page.get_by_role('button',name='Confirmar código',exact=True).click()
    expect(page.locator('#mfa-backup')).to_be_visible()
    assert len(page.locator('#mfa-codigos').inner_text().splitlines())==10
    expect(page.locator('#mfa-status')).to_contain_text('Proteção ativa')


def test_assistente_exige_revisao_e_preenche_formulario(page):
    registrar_pela_interface(page)
    page.goto(url('planejamento.html'),wait_until='domcontentloaded');essenciais(page)
    page.get_by_text('Descrever meu churrasco em uma frase',exact=True).click()
    page.locator('#assistente-texto').fill('25 pessoas incluindo 6 crianças, 4 horas, orçamento de R$ 800')
    page.get_by_role('button',name='Preparar sugestão').click()
    expect(page.locator('#assistente-preview')).to_be_visible()
    expect(page.locator('#assistente-parametros')).to_contain_text('19 adultos')
    page.get_by_role('button',name='Revisei. Aplicar ao formulário').click()
    expect(page.locator('#campo-adultos')).to_have_value('19')
    expect(page.locator('#campo-criancas')).to_have_value('6')


def test_analytics_somente_apos_escolha(page):
    requests=[]
    page.on('request',lambda req: requests.append(req.url) if '/api/growth/eventos' in req.url else None)
    page.goto(url('index.html'),wait_until='domcontentloaded')
    expect(page.get_by_role('button',name='Permitir métricas',exact=True)).to_be_visible()
    assert not requests
    page.get_by_role('button',name='Permitir métricas',exact=True).click()
    page.wait_for_function("localStorage.getItem('churrasplan_analytics') === 'permitido'")
    page.wait_for_timeout(200)
    assert requests
