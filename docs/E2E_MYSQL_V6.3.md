# E2E e MySQL real — v6.3

## Testes backend

```bash
cd BackEnd/Python
pip install -r requirements-dev.txt
pytest -q tests
```

## MySQL real
Defina um banco descartável:

```bash
export MYSQL_TEST_URL='mysql+pymysql://usuario:senha@127.0.0.1:3306/churrasplan_test?charset=utf8mb4'
export DATABASE_URL="$MYSQL_TEST_URL"
alembic upgrade head
alembic check
pytest -q tests_mysql
```

Os testes verificam head, `utf8mb4`, FKs/cascade, JSON, consentimentos e ausência do IP bruto legado na tabela de sessões.

## E2E Playwright
Com API em `127.0.0.1:8000` e frontend em `127.0.0.1:5500`:

```bash
python -m playwright install chromium
E2E_BASE_URL=http://127.0.0.1:5500 pytest -q e2e
```

Cenários:
- fluxo público até resultado;
- cadastro + conta + recursos LGPD;
- PWA;
- viewport mobile/overflow/alvos de toque.

## CI
O GitHub Actions sobe um `mysql:8.4` real e executa migrations/testes. O job E2E usa outro banco MySQL isolado.

No ambiente de geração desta release, a navegação Chromium local é bloqueada por política administrativa (`ERR_BLOCKED_BY_ADMINISTRATOR`) e não existe daemon MySQL/Docker. Isso não altera os testes entregues; significa apenas que MySQL real + browser completo devem ser executados pelo CI/staging, e não foram simulados como se tivessem rodado localmente.
