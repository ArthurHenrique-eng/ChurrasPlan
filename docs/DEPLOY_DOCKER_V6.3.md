# Deploy Docker — ChurrasPlan v6.3

## Desenvolvimento local

```bash
cp .env.docker.example .env
docker compose up --build
```

Aplicação: `http://localhost:8080`.

A composição sobe MySQL 8.4, aguarda o banco, executa `alembic upgrade head`, inicia a API e depois o frontend.

## Produção com HTTPS automático

Use a composição independente `docker-compose.production.yml`.

```bash
cp .env.production.example .env.production
# edite TODOS os segredos e domínio
set -a
. ./.env.production
set +a
docker compose -f docker-compose.production.yml up -d --build
```

No Windows PowerShell, defina as variáveis por um arquivo/gerenciador compatível com seu processo de deploy; não faça commit do arquivo contendo segredos.

### Topologia

```text
Internet
  ↓ 80/443
Caddy (TLS)
  ├─ /api, /docs, /openapi.json → FastAPI
  └─ demais rotas              → Nginx frontend
                                  ↓
                               MySQL (rede interna)
```

MySQL e FastAPI não publicam portas no host na composição de produção.

## DNS
Crie um registro A/AAAA para `APP_DOMAIN` apontando ao servidor. Caddy só consegue emitir certificado quando o domínio é alcançável nas portas 80/443.

## Primeiro administrador

```bash
docker compose -f docker-compose.production.yml exec \
  -e ADMIN_EMAIL=admin@seudominio.com \
  -e ADMIN_PASSWORD='SENHA_FORTE' \
  -e ADMIN_NAME='Administrador' \
  backend python scripts/create_admin.py
```

Nunca salve a senha administrativa em código, README ou histórico do shell de produção.

## Banco e migrations

Verifique:

```bash
docker compose -f docker-compose.production.yml exec backend alembic current
docker compose -f docker-compose.production.yml exec backend alembic check
```

Head esperado da v6.3: `20260918_0005`.

## Backup
Exemplo manual:

```bash
docker compose -f docker-compose.production.yml exec -T db \
  mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE" \
  > backup-churrasplan.sql
```

Automatize backups fora do volume primário e teste restauração periodicamente.

## Atualização

1. backup;
2. deploy em staging;
3. `alembic upgrade head` em staging;
4. E2E;
5. publicação;
6. migrations de produção;
7. smoke test `/api/health/ready`.

## Google Maps/Places
A chave de servidor deve ser restrita à Places API e a chave JavaScript deve ser restrita por HTTP referrer ao domínio publicado. Nunca reutilize uma chave irrestrita.
