import os
import platform
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


def encontrar_navegador_local():
    """
    Localiza um navegador Chromium compatível.

    Ordem:
    1. CHROMIUM_PATH informado pelo usuário.
    2. Navegadores conhecidos no Windows.
    3. Navegadores conhecidos no Linux.
    4. None: Playwright utiliza seu Chromium gerenciado.
    """

    configurado = os.getenv("CHROMIUM_PATH")

    if configurado:
        caminho = Path(configurado)

        if not caminho.exists():
            raise RuntimeError(
                f"CHROMIUM_PATH aponta para um arquivo inexistente: "
                f"{configurado}"
            )

        return str(caminho)

    sistema = platform.system()

    candidatos = []

    if sistema == "Windows":
        candidatos = [
            Path(
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            ),
            Path(
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
            ),
            Path(
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            ),
            Path(
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            ),
        ]

    elif sistema == "Linux":
        candidatos = [
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
        ]

    for caminho in candidatos:
        if caminho.exists():
            return str(caminho)

    return None


@pytest.fixture(scope="session")
def browser():
    """
    Browser usado nos testes E2E.

    Localmente pode usar Edge ou Chrome.
    No GitHub Actions usa o Chromium instalado pelo Playwright.
    """

    executable = encontrar_navegador_local()

    with sync_playwright() as playwright:
        kwargs = {
            "headless": True,
            "args": ["--no-sandbox"],
        }

        if executable:
            kwargs["executable_path"] = executable

        browser = playwright.chromium.launch(**kwargs)

        yield browser

        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(
        viewport={
            "width": 1440,
            "height": 1000,
        }
    )

    page = context.new_page()

    yield page

    context.close()