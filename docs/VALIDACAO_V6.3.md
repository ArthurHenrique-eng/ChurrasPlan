# Validação da release v6.3

Data da preparação: 2026-09-18.

## Executado neste ambiente

- `pytest -q BackEnd/Python/tests`: **90 passed**;
- `python -m compileall`: OK;
- instalação Alembic limpa até `20260918_0005`: OK;
- `alembic check` em banco migrado: sem operações pendentes;
- upgrade `20260918_0004 -> 20260918_0005` com usuário/sessão legados: OK;
- IP bruto legado removido; usuário preservado;
- `tests_mysql` coletam corretamente e ficam skipped sem `MYSQL_TEST_URL`;
- `schema.sql` x ORM: **21 tabelas alinhadas**;
- JavaScript: todos os arquivos de `FrontEnd/js` + `sw.js` passam em `node --check`;
- frontend: **20 HTML** verificados quanto a referências/estrutura básica;
- CSS: **11 arquivos**, sem erros de parsing pelo validador disponível;
- manifest PWA e ícones: referências presentes;
- OpenAPI: **58 paths / 62 operações**, versão `6.3.0`;
- YAML: compose dev, override legado, compose produção e GitHub Actions parseiam corretamente.

## Não executado localmente por limitação do ambiente

### MySQL 8 real
Este runtime não possui daemon MySQL nem Docker. A release inclui:
- `tests_mysql/`;
- job CI com `mysql:8.4`;
- `alembic upgrade head` + `alembic check` + testes específicos.

Esse job deve ficar verde no repositório e ser repetido em staging antes do lançamento.

### Navegação E2E Chromium
O Chromium deste runtime retorna `ERR_BLOCKED_BY_ADMINISTRATOR` ao navegar para servidores HTTP locais. As requisições HTTP diretas funcionam, mas a política impede validar a navegação completa aqui.

A release inclui suíte Playwright e job GitHub Actions com Chromium + MySQL real. Não foi registrado um falso “E2E passou” localmente.

### Build Docker real
O binário Docker não existe neste runtime. Os YAMLs foram analisados estruturalmente e o CI possui job para `docker compose config` e build das imagens.

## Critério de promoção para produção

A v6.3 só deve ser promovida após os jobs GitHub Actions `mysql-real`, `security-static`, `docker-build` e `e2e` ficarem verdes e o mesmo conjunto ser validado no ambiente de staging.
