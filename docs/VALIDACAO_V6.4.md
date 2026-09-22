# Validação — ChurrasPlan v6.4.0

Validações executadas no artefato desta release:

- `pytest -q tests`: **96 passed**;
- `scripts/validate_schema.py`: **schema alinhado ao ORM, 21 tabelas**;
- `scripts/validate_frontend.py`: **20 HTML verificados**;
- `node --check` em todos os arquivos `FrontEnd/js/*.js` e `FrontEnd/sw.js`: **OK**;
- `python -m compileall -q BackEnd/Python`: **OK**;
- OpenAPI com banco SQLite de inspeção: **58 paths / 64 operações**, versão **6.4.0**;
- `tests_mysql`: **4 testes preparados**, incluindo verificação de InnoDB; neste ambiente de empacotamento foram ignorados por ausência de `MYSQL_TEST_URL`/servidor MySQL real.

A integração Google Places possui teste com resposta mockada para garantir que a chave de servidor não é exposta ao frontend e que estabelecimentos `CLOSED_PERMANENTLY` não aparecem.

Para validação final no ambiente local/CI com credenciais reais:

```powershell
.\scripts\test_all.ps1 -MySQL
```

E, quando o Chromium/Playwright estiver disponível:

```powershell
.\scripts\test_all.ps1 -MySQL -E2E
```

A chamada real ao Google Maps/Places depende das chaves do projeto Google Cloud e não é feita pela suíte unitária para evitar custo, dependência de rede e uso de credenciais reais em CI.
