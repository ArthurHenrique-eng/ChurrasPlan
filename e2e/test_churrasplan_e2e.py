import os
import uuid

from playwright.sync_api import Page, expect


FRONTEND = os.getenv(
    "E2E_BASE_URL",
    "http://127.0.0.1:5500",
)


def url(path: str) -> str:
    return f"{FRONTEND.rstrip('/')}/{path.lstrip('/')}"


def test_home_e_fluxo_basico_ate_resultado(page: Page):
    page.goto(
        url("index.html"),
        wait_until="domcontentloaded",
    )

    expect(
        page.get_by_role(
            "heading",
            name="Menos conta. Mais churrasco.",
        )
    ).to_be_visible()

    page.goto(
        url("planejamento.html"),
        wait_until="domcontentloaded",
    )

    # Tipo de evento é obrigatório no fluxo atual.
    page.locator('[data-evento="almoco"]').click()

    page.locator("#campo-adultos").fill("6")
    page.locator("#campo-criancas").fill("2")
    page.locator("#campo-adultos-alcool").fill("3")
    page.locator("#campo-orcamento").fill("800")

    page.locator(
        "#form-planejamento button[type=submit]"
    ).click()

    page.wait_for_url(
        "**/carnes.html",
        timeout=15000,
    )

    primeira = page.locator(
        'input[data-carne="picanha"]'
    )
    primeira.check()

    page.locator(
        'input[data-percentual="picanha"]'
    ).fill("100")

    expect(
        page.locator("#botao-avancar")
    ).to_be_enabled()

    page.locator("#botao-avancar").click()

    page.wait_for_url(
        "**/bebidas.html",
        timeout=15000,
    )

    page.locator(
        "#form-bebidas button[type=submit]"
    ).click()

    page.wait_for_url(
        "**/extras.html",
        timeout=15000,
    )

    page.locator(
        "#form-extras button[type=submit]"
    ).click()

    page.wait_for_url(
        "**/resultado.html",
        timeout=15000,
    )

    expect(
        page.locator("#conteudo-resultado")
    ).to_be_visible(timeout=15000)

    expect(
        page.locator("#bloco-pessoas")
    ).to_have_text("8")

    expect(
        page.locator("#bloco-orcamento")
    ).to_contain_text("Orçamento")

    # O CI carrega preços demonstrativos para o catálogo.
    expect(
        page.locator("#bloco-custo-pessoa")
    ).not_to_have_text("sem preços")

    expect(
        page.locator("#divisao-valor")
    ).not_to_have_text("indisponível")

    antes = page.locator(
        "#divisao-valor"
    ).inner_text()

    page.locator("#divisao-mais").click()

    expect(
        page.locator("#divisao-pessoas")
    ).to_have_value("3")

    expect(
        page.locator("#divisao-valor")
    ).not_to_have_text(antes)


def test_cadastro_login_conta_e_lgpd(page: Page):
    email = (
        f"e2e-{uuid.uuid4().hex[:10]}"
        "@example.com"
    )

    page.goto(
        url("cadastro.html"),
        wait_until="domcontentloaded",
    )

    page.locator("#auth-nome").fill(
        "Usuário E2E"
    )
    page.locator("#auth-email").fill(email)
    page.locator("#auth-senha").fill(
        "SenhaE2E12345"
    )

    page.locator("#aceite-termos").check()
    page.locator("#aceite-privacidade").check()

    page.locator(
        "#auth-form button[type=submit]"
    ).click()

    page.wait_for_url(
        "**/minha-conta.html",
        timeout=15000,
    )

    expect(page).to_have_url(
    url("minha-conta.html")
    )

    expect(
        page.locator("#conta-saudacao")
    ).to_contain_text("Usuário")

    expect(
        page.locator("#exportar-dados")
    ).to_be_visible()

    expect(
        page.locator("#excluir-conta")
    ).to_be_visible()


def test_convite_publico_renderiza_estado_visivel(page: Page):
    page.goto(
        url("convite.html"),
        wait_until="domcontentloaded",
    )

    expect(
        page.get_by_role(
            "heading",
            name="Você foi convidado para um churrasco.",
        )
    ).to_be_visible()

    expect(
        page.get_by_role(
            "heading",
            name="Não foi possível abrir este convite.",
        )
    ).to_be_visible(timeout=10000)


def test_pwa_manifest_e_service_worker(page: Page):
    response = page.request.get(
        url("manifest.webmanifest")
    )

    assert response.ok

    data = response.json()
    assert data["name"] == "ChurrasPlan"

    page.goto(
        url("index.html"),
        wait_until="domcontentloaded",
    )

    sw = page.request.get(
        url("sw.js")
    )

    assert sw.ok


def test_mobile_sem_overflow_horizontal_e_com_alvos_de_toque(
    browser,
):
    context = browser.new_context(
        viewport={
            "width": 390,
            "height": 844,
        },
        is_mobile=True,
        has_touch=True,
        device_scale_factor=2,
    )

    mobile = context.new_page()

    try:
        # Apenas páginas públicas neste teste.
        paginas = [
            "index.html",
            "planos.html",
            "planejamento.html",
            "privacidade.html",
            "convite.html",
        ]

        for pagina in paginas:
            mobile.goto(
                url(pagina),
                wait_until="domcontentloaded",
            )

            largura = mobile.evaluate(
                """
                Math.max(
                    document.documentElement.scrollWidth,
                    document.body.scrollWidth
                )
                """
            )

            viewport = mobile.evaluate(
                "window.innerWidth"
            )

            assert largura <= viewport + 2, (
                f"overflow horizontal em "
                f"{pagina}: "
                f"{largura}px > {viewport}px"
            )

        mobile.goto(
            url("planejamento.html"),
            wait_until="domcontentloaded",
        )

        alvo = mobile.locator(
            "#form-planejamento "
            "button[type=submit]"
        )

        expect(alvo).to_be_visible()

        caixa = alvo.bounding_box()

        assert caixa
        assert caixa["height"] >= 44

    finally:
        context.close()

def test_parceiro_seleciona_genericos_apos_ativacao(page: Page):
    email = f"e2e-parceiro-catalogo-{uuid.uuid4().hex[:10]}@example.com"
    page.goto(url("cadastro.html"), wait_until="domcontentloaded")
    page.locator("#auth-nome").fill("Parceiro Catálogo E2E")
    page.locator("#auth-email").fill(email)
    page.locator("#auth-senha").fill("SenhaCatalogoE2E123")
    page.locator("#aceite-termos").check()
    page.locator("#aceite-privacidade").check()
    page.locator("#auth-form button[type=submit]").click()
    page.wait_for_url("**/minha-conta.html", timeout=15000)

    page.goto(url("parceiro.html"), wait_until="domcontentloaded")
    page.locator("#ativar-parceiro").click()
    page.wait_for_function(
        "() => document.querySelectorAll('#prod-categoria option').length > 1",
        timeout=15000,
    )
    page.locator("#prod-categoria").select_option(label="Bebidas")
    expect(page.locator("#prod-pai")).to_be_enabled()
    assert any("Água" in texto for texto in page.locator("#prod-pai option").all_text_contents())
    page.locator("#prod-categoria").select_option(label="Limpeza")
    assert any("Detergente" in texto for texto in page.locator("#prod-pai option").all_text_contents())


def test_planos_publicos_visiveis_e_checkout_bloqueado_sem_sandbox(page: Page):
    """Plano deve ser descoberto diretamente na home, sem pagamentos reais."""
    page.goto(url("index.html"), wait_until="domcontentloaded")
    home_link = page.get_by_role("link", name="Planos", exact=True)
    expect(home_link).to_be_visible()
    home_link.click()
    page.wait_for_url("**/planos.html", timeout=10000)

    expect(page.get_by_role("heading", name="Escolha seu plano.")).to_be_visible()
    expect(page.get_by_role("heading", name="Premium")).to_be_visible()
    expect(page.get_by_role("heading", name="Pro")).to_be_visible()
    expect(page.get_by_role("heading", name="Business")).to_be_visible()
    expect(page.get_by_text("Ambiente de testes Stripe.", exact=False)).to_be_visible()
    # O CI não fornece nenhuma chave Stripe; nunca oferecer Checkout fictício.
    for slug in ("premium", "pro", "business"):
        expect(page.locator(f'[data-plano="{slug}"]')).to_be_disabled(timeout=15000)
        expect(page.locator("#preco-" + slug)).to_contain_text("Indisponível no teste")
    page.locator("#planos-periodo").select_option("anual")
    for slug in ("premium", "pro", "business"):
        expect(page.locator(f'[data-plano="{slug}"]')).to_be_disabled()


def test_planos_logo_mantem_tamanho_do_cabecalho(page: Page):
    """O cabeçalho não pode ampliar os assets originais da marca."""
    page.set_viewport_size({"width": 1366, "height": 900})
    page.goto(url("planos.html"), wait_until="networkidle")

    icon = page.locator(".planos-topbar .planos-brand-icon")
    name = page.locator(".planos-topbar .planos-brand-name")
    brand = page.locator(".planos-topbar .planos-brand")
    expect(icon).to_be_visible()
    expect(name).to_have_text("ChurrasPlan")

    icon_box = icon.bounding_box()
    name_box = name.bounding_box()
    brand_box = brand.bounding_box()
    header_box = page.locator(".planos-topbar").bounding_box()
    nav_box = page.locator(".planos-topbar nav").bounding_box()
    assert icon_box and name_box and brand_box and header_box and nav_box
    assert icon_box["width"] <= 46 and icon_box["height"] <= 46
    assert name_box["width"] <= 215 and name_box["height"] <= 38
    assert brand_box["width"] <= 260
    assert header_box["height"] < 130
    assert nav_box["x"] > brand_box["x"] + brand_box["width"]


def test_planos_logo_compacta_em_tela_pequena(page: Page):
    """A marca e navegação devem caber no layout mobile."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(url("planos.html"), wait_until="networkidle")
    icon_box = page.locator(".planos-brand-icon").bounding_box()
    name_box = page.locator(".planos-brand-name").bounding_box()
    assert icon_box and name_box
    assert icon_box["width"] <= 40 and icon_box["height"] <= 40
    assert name_box["width"] <= 205
    assert page.evaluate("document.documentElement.scrollWidth") <= 392
