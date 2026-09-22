import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def browser():
    """Browser fixture independente de pytest-playwright para execução local e CI."""
    executable = os.getenv("CHROMIUM_PATH")
    if not executable and Path("/usr/bin/chromium").exists():
        executable = "/usr/bin/chromium"
    with sync_playwright() as playwright:
        kwargs = {"headless": True, "args": ["--no-sandbox"]}
        if executable:
            kwargs["executable_path"] = executable
        browser = playwright.chromium.launch(**kwargs)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    yield page
    context.close()
