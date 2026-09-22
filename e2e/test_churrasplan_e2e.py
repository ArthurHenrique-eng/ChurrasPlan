import os
import uuid

import pytest
from playwright.sync_api import Page, expect

FRONTEND = os.getenv("E2E_BASE_URL", "http://127.0.0.1:5500")


def url(path: str) -> str:
    return f"{FRONTEND.rstrip('/')}/{path.lstrip('/')}"


def test_home_e_fluxo_basico_ate_resultado(page: Page):
    page.goto(url("index.html"))
    expect(page.get_by_role("heading", name="Menos conta. Mais churrasco.")).to_be_visible()
    page.goto(url("planejamento.html"))
    page.locator("#campo-adultos").fill("6")
    page.locator("#campo-criancas").fill("2")
    page.locator("#campo-adultos-alcool").fill("3")
    page.locator("#campo-orcamento").fill("800")
    page.locator("#form-planejamento").evaluate("form => form.requestSubmit()")
    page.wait_for_url("**/carnes.html")

    primeira = page.locator('input[data-carne="picanha"]')
    primeira.check()
    page.locator('input[data-percentual="picanha"]').fill("100")
    expect(page.locator("#botao-avancar")).to_be_enabled()
    page.locator("#form-carnes").evaluate("form => form.requestSubmit()")
    page.wait_for_url("**/bebidas.html")

    page.locator("#form-bebidas").evaluate("form => form.requestSubmit()")
    page.wait_for_url("**/extras.html")
    page.locator("#form-extras").evaluate("form => form.requestSubmit()")
    page.wait_for_url("**/resultado.html")
    expect(page.locator("#conteudo-resultado")).to_be_visible(timeout=15000)
    expect(page.locator("#bloco-pessoas")).to_have_text("8")
    expect(page.locator("#bloco-orcamento")).to_contain_text("Orçamento")

    # O ambiente E2E carrega preços demonstrativos para o catálogo inteiro.
    # Custo por pessoa e divisão precisam funcionar de ponta a ponta.
    expect(page.locator("#bloco-custo-pessoa")).not_to_have_text("sem preços")
    expect(page.locator("#divisao-valor")).not_to_have_text("indisponível")
    antes = page.locator("#divisao-valor").inner_text()
    page.locator("#divisao-mais").click()
    expect(page.locator("#divisao-pessoas")).to_have_value("3")
    expect(page.locator("#divisao-valor")).not_to_have_text(antes)


def test_cadastro_login_conta_e_lgpd(page: Page):
    email = f"e2e-{uuid.uuid4().hex[:10]}@example.com"
    page.goto(url("cadastro.html"))
    page.locator("#auth-nome").fill("Usuário E2E")
    page.locator("#auth-email").fill(email)
    page.locator("#auth-senha").fill("SenhaE2E12345")
    page.locator("#aceite-termos").check()
    page.locator("#aceite-privacidade").check()
    page.locator("#auth-form").evaluate("form => form.requestSubmit()")
    page.wait_for_url("**/minha-conta.html", timeout=15000)
    expect(page.locator("#conta-saudacao")).to_contain_text("Usuário")
    expect(page.locator("#exportar-dados")).to_be_visible()
    expect(page.locator("#excluir-conta")).to_be_visible()


def test_pwa_manifest_e_service_worker(page: Page):
    response = page.request.get(url("manifest.webmanifest"))
    assert response.ok
    data = response.json()
    assert data["name"] == "ChurrasPlan"
    page.goto(url("index.html"))
    # Service workers podem ser bloqueados em alguns modos do navegador; o arquivo
    # precisa ao menos estar publicamente disponível e sem erro sintático de rede.
    sw = page.request.get(url("sw.js"))
    assert sw.ok


def test_mobile_sem_overflow_horizontal_e_com_alvos_de_toque(browser):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
        device_scale_factor=2,
    )
    mobile = context.new_page()
    try:
        for pagina in ["index.html", "planejamento.html", "minha-conta.html"]:
            mobile.goto(url(pagina))
            largura = mobile.evaluate("Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            viewport = mobile.evaluate("window.innerWidth")
            assert largura <= viewport + 2, f"overflow horizontal em {pagina}: {largura}px > {viewport}px"

        mobile.goto(url("planejamento.html"))
        alvo = mobile.locator("#form-planejamento button[type=submit]")
        caixa = alvo.bounding_box()
        assert caixa and caixa["height"] >= 44
    finally:
        context.close()
