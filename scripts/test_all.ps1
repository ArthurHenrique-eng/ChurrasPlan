param(
    [switch]$MySQL,
    [switch]$E2E,
    [switch]$InstallBrowser
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $Root "BackEnd\Python"

function Assert-Success {
    param([string]$Etapa)
    if ($LASTEXITCODE -ne 0) {
        throw "ERRO: $Etapa falhou com exit code $LASTEXITCODE."
    }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " ChurrasPlan - Suite completa de testes" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "== Backend: compilacao Python ==" -ForegroundColor Cyan
Push-Location $Backend
python -m compileall -q .
Assert-Success "compileall"

Write-Host "== Backend: unitarios e integracao ==" -ForegroundColor Cyan
python -m pytest -q tests
Assert-Success "pytest backend"
Pop-Location

Write-Host "== Schema e frontend estatico ==" -ForegroundColor Cyan
Push-Location $Root
python scripts/validate_schema.py
Assert-Success "validacao schema.sql x ORM"
python scripts/validate_frontend.py
Assert-Success "validacao frontend"
Get-ChildItem "FrontEnd\js" -Filter "*.js" -Recurse | ForEach-Object {
    node --check $_.FullName
    Assert-Success "JavaScript $($_.Name)"
}
node --check "FrontEnd\sw.js"
Assert-Success "Service Worker"
Pop-Location

if ($MySQL) {
    if (-not $env:MYSQL_TEST_URL) {
        throw 'MYSQL_TEST_URL nao definido. Ex.: mysql+pymysql://root:@127.0.0.1:3306/churrasplan_test?charset=utf8mb4'
    }

    Write-Host ""
    Write-Host "== MySQL real: preparando banco ==" -ForegroundColor Cyan

    $bootstrapMySQL = @'
import os
import pymysql
from sqlalchemy.engine import make_url

url = make_url(os.environ["MYSQL_TEST_URL"])
database = url.database
if not database:
    raise SystemExit("MYSQL_TEST_URL precisa informar um banco.")
if not database.lower().endswith("_test"):
    raise SystemExit(f"Por seguranca, o banco de testes precisa terminar em '_test'. Recebido: {database}")

connection = pymysql.connect(
    host=url.host or "127.0.0.1",
    port=url.port or 3306,
    user=url.username,
    password=url.password or "",
    charset="utf8mb4",
    autocommit=True,
)
safe_database = database.replace("`", "``")
with connection.cursor() as cursor:
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{safe_database}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
connection.close()
print(f"Banco MySQL de teste pronto: {database}")
'@

    $bootstrapMySQL | python -
    Assert-Success "criacao/verificacao do banco MySQL"

    $oldDatabaseUrl = $env:DATABASE_URL
    $oldPythonPath = $env:PYTHONPATH
    try {
        $env:DATABASE_URL = $env:MYSQL_TEST_URL
        $env:PYTHONPATH = $Backend
        Push-Location $Backend

        Write-Host "== MySQL: Alembic upgrade head ==" -ForegroundColor Cyan
        alembic upgrade head
        Assert-Success "alembic upgrade head"

        Write-Host "== MySQL: Alembic check ==" -ForegroundColor Cyan
        alembic check
        Assert-Success "alembic check"

        Write-Host "== MySQL: testes reais ==" -ForegroundColor Cyan
        python -m pytest -q tests_mysql
        Assert-Success "pytest MySQL"
        Pop-Location
    }
    finally {
        $env:DATABASE_URL = $oldDatabaseUrl
        $env:PYTHONPATH = $oldPythonPath
    }
}

if ($E2E) {
    Write-Host ""
    Write-Host "== Playwright E2E ==" -ForegroundColor Cyan
    if ($InstallBrowser) {
        Write-Host "Instalando Chromium do Playwright..." -ForegroundColor Yellow
        python -m playwright install chromium
        Assert-Success "instalacao Chromium Playwright"
    }
    if (-not $env:E2E_BASE_URL) { $env:E2E_BASE_URL = "http://127.0.0.1:5500" }
    Push-Location $Root
    python -m pytest -q e2e
    Assert-Success "testes E2E"
    Pop-Location
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host " TODOS OS TESTES SELECIONADOS PASSARAM" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
