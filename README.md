# ChurrasPlan v6.5.0 — Geoapify + administração segura

O **ChurrasPlan** é uma plataforma Full Stack para planejar churrascos do início ao fim: convidados, quantidades, restrições alimentares, orçamento, lista/checklist de compras, preços, histórico, convites/RSVP, parceiros e otimização de onde comprar.

A v6.5.0 preserva a base production-ready da v6.4 e substitui a integração Google Maps/Places por Geoapify Places, Address Autocomplete e Map Tiles, mantendo o bootstrap seguro do administrador e o pipeline completo de testes.

## Estado da plataforma

### Fluxo principal
- adultos e crianças;
- consumidores de álcool;
- vegetarianos/veganos e restrições;
- orçamento opcional;
- carnes, bebidas, carvão, gelo, extras e acompanhamentos;
- necessidade física separada da quantidade comercial de compra;
- custo estimado completo/parcial;
- checklist e preço realmente pago;
- divisão opcional de custos.

### Conta
- cadastro, login, logout;
- verificação de e-mail;
- recuperação de senha;
- sessões em cookies HttpOnly;
- CSRF;
- histórico e repetição de churrascos;
- convites públicos com RSVP;
- área “Onde comprar”.

### Produtos, parceiros e compras
- produto genérico + SKU comercial;
- marca, variante, fabricante, EAN e embalagem;
- estabelecimentos e ofertas;
- parceiros verificados;
- comparação por preço, distância, avaliação e equilíbrio;
- otimização multiestabelecimento;
- suporte opcional a Geoapify Places, Address Autocomplete e Map Tiles;
- métricas agregadas de parceiros.

### Administração
- papel `admin`;
- dashboard;
- gestão de usuários/papéis/status;
- moderação de estabelecimentos;
- auditoria administrativa;
- limpeza de eventos técnicos antigos.

## Estrutura

```text
ChurrasPlan/
├── BackEnd/Python/
│   ├── alembic/
│   ├── database/
│   ├── middleware/
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   ├── sql/
│   ├── tests/
│   ├── tests_mysql/
│   └── scripts/
├── FrontEnd/
│   ├── assets/
│   ├── css/
│   ├── js/
│   ├── manifest.webmanifest
│   └── sw.js
├── e2e/
├── deploy/
├── docs/
├── scripts/
├── .github/workflows/ci.yml
├── docker-compose.yml
└── docker-compose.production.yml
```

## Banco e Alembic

O Alembic é a fonte de verdade da evolução do banco.

Head atual:

```text
20260922_0006
```

Cadeia:

```text
20260917_0001  baseline consistente
20260918_0002  contas/orçamento/RSVP/SKUs/parceiros
20260918_0003  alinhamentos de schema
20260918_0004  métricas agregadas de estabelecimentos
20260918_0005  LGPD, rate limiting e auditoria admin
20260922_0006  restaura defaults de timestamps em usuarios
```

`BackEnd/Python/sql/schema.sql` representa uma **instalação nova** no head atual. Para banco existente, use migrations.

## Rodar com Docker — desenvolvimento

Pré-requisito: Docker + Docker Compose.

```bash
cp .env.docker.example .env
docker compose up --build
```

Abra:

```text
http://localhost:8080
```

Swagger:

```text
http://localhost:8080/docs
```

A stack sobe MySQL 8.4, aplica migrations, carrega um catálogo/preços **demonstrativos** em desenvolvimento, inicia FastAPI e serve o frontend via Nginx.

Os preços de desenvolvimento existem somente para exercitar orçamento, custo por pessoa e divisão. Para desabilitá-los:

```bash
LOAD_DEMO_DATA=false docker compose up --build
```

Nunca trate esses valores como preços reais de mercado.

## Rodar sem Docker

### Backend

```bash
cd BackEnd/Python
python -m venv .venv
# ative a venv
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
# Opcional, recomendado para desenvolvimento local:
python scripts/seed_demo.py
uvicorn main:app --reload --port 8000
```

Sem ofertas cadastradas, o sistema não inventa preços. Com parte da cesta precificada, custo por pessoa e divisão aparecem como **estimativa parcial**; quando todos os itens têm preço, passam a ser estimativas completas.

### Frontend

Em outro terminal:

```bash
cd FrontEnd
python -m http.server 5500
```

Acesse `http://127.0.0.1:5500`.

## Health checks

```text
GET /api/health
```
Liveness do processo.

```text
GET /api/health/ready
```
Readiness incluindo conexão com o banco.

## Segurança da v6.3

- PBKDF2-HMAC-SHA256 com salt aleatório para senhas;
- sessão opaca; só o hash do segredo fica no banco;
- cookie de sessão HttpOnly;
- cookies Secure em produção;
- CSRF para mutações autenticadas;
- tokens de verificação/reset de uso único e persistidos por hash;
- rate limiting de cadastro/login/recuperação/RSVP;
- HMAC para chaves técnicas; IP bruto não é persistido em sessão;
- limite de corpo de requisição;
- security headers + HSTS;
- CORS e hosts explícitos;
- trilha de auditoria administrativa;
- configuração de produção falha cedo quando insegura;
- `pip-audit` e `bandit` no CI.

Em produção, a aplicação também recusa banco diferente de MySQL/PyMySQL.

## LGPD / privacidade

Implementado tecnicamente:
- Termos e Privacidade versionados;
- aceite obrigatório dos documentos necessários;
- marketing separado e opcional;
- exportação da conta em JSON;
- exclusão da conta com reautenticação;
- minimização de métricas;
- Política de Privacidade, Termos e Política de Cookies.

**Antes de publicação comercial**, os documentos precisam receber dados reais do controlador (razão social/CNPJ/canal de privacidade), fornecedores efetivamente utilizados e revisão jurídica.

## Admin inicial

Não existe senha administrativa hardcoded no repositório. No Windows, use o helper seguro da raiz: ele pede a senha com `Read-Host -AsSecureString`, promove/cria a conta, marca o e-mail do admin como verificado e invalida sessões antigas quando a senha é redefinida.

```powershell
.\scripts\set_admin.ps1 -Email "admin@example.com" -Name "Administrador"
```

No Linux/macOS, após banco/migrations:

```bash
cd BackEnd/Python
ADMIN_EMAIL=admin@example.com \
ADMIN_PASSWORD='uma-senha-forte' \
ADMIN_NAME='Administrador' \
ADMIN_RESET_PASSWORD=true \
python scripts/create_admin.py
```

Nunca grave a senha administrativa em `.env.example`, seed SQL, código-fonte ou histórico do Git.

## PWA

A aplicação possui:
- manifest;
- ícones 192/512/maskable;
- service worker;
- cache de assets e páginas públicas seguras;
- fallback offline;
- aviso de conectividade;
- prompt de instalação quando o navegador disponibiliza.

A API e páginas privadas não são cacheadas pelo service worker. Escritas como checklist/login continuam exigindo conexão; não há fila de sincronização offline nesta versão.

## Testes

### Backend

```bash
cd BackEnd/Python
pytest -q tests
```

### MySQL real

```bash
export MYSQL_TEST_URL='mysql+pymysql://.../churrasplan_test?charset=utf8mb4'
export DATABASE_URL="$MYSQL_TEST_URL"
alembic upgrade head
alembic check
pytest -q tests_mysql
```

### E2E

```bash
python -m playwright install chromium
E2E_BASE_URL=http://127.0.0.1:5500 pytest -q e2e
```

### Rodar a bateria local de uma vez

Windows PowerShell:

```powershell
.\scripts\test_all.ps1
```

Linux/macOS/Git Bash:

```bash
./scripts/test_all.sh
```

Os scripts também suportam MySQL real e E2E por opção/variável de ambiente.

### Validações auxiliares

```bash
python scripts/validate_frontend.py
python scripts/validate_schema.py
find FrontEnd/js -name '*.js' -print0 | xargs -0 -n1 node --check
node --check FrontEnd/sw.js
```

## CI/CD

`.github/workflows/ci.yml` executa:
1. backend em SQLite;
2. migrations/testes contra MySQL 8.4 real;
3. frontend estático;
4. auditoria de dependências/segurança;
5. build das imagens Docker e validação de compose;
6. E2E Chromium contra MySQL real.

A etapa de **deploy** não está ligada a um provedor específico. Isso é intencional: primeiro deve ser definido onde staging/produção serão hospedados e como os segredos serão gerenciados.

## Produção com Docker + HTTPS

A composição recomendada é a independente:

```bash
cp .env.production.example .env.production
# preencha domínio e segredos
# carregue as variáveis conforme seu ambiente
docker compose -f docker-compose.production.yml up -d --build
```

Ela usa:

```text
Caddy/HTTPS
  ├─ /api → FastAPI
  └─ site → Nginx frontend
       ↓
MySQL em rede interna
```

Veja `docs/DEPLOY_DOCKER_V6.3.md`.

## Geoapify

A v6.5 usa Geoapify para mapa, busca de estabelecimentos próximos e autocomplete de endereços. A aplicação separa a chave pública dos tiles da chave de servidor:

```dotenv
GEOAPIFY_ENABLED=true
GEOAPIFY_SERVER_API_KEY=chave_restrita_ao_backend
GEOAPIFY_MAP_API_KEY=chave_publica_restrita_aos_dominios
```

Em desenvolvimento, as duas variáveis podem apontar temporariamente para a mesma chave. Em produção, prefira duas chaves distintas: restrinja a chave de servidor por IP/API e a chave do mapa por HTTP referrer/origin.

Fluxo implementado: usuário autenticado abre **Onde comprar** → usa geolocalização ou digita um endereço → o backend consulta Address Autocomplete/Places da Geoapify → o frontend desenha o mapa com Leaflet + Geoapify Map Tiles → a lista mostra distância e origem Geoapify → a otimização da cesta continua usando somente ofertas/preços próprios do ChurrasPlan.

Sem as chaves, a página continua funcional com os estabelecimentos cadastrados e a otimização própria; mapa, autocomplete e busca externa ficam desativados de forma graciosa.

## Integrações externas restantes

Ainda exigem credenciais reais:
- SMTP para verificação/reset de e-mail;
- Geoapify conforme configuração acima;
- eventual provedor de pagamento, ainda não conectado.

Preços demonstrativos do seed **não são preços reais de mercado**.

## Documentação desta etapa

- `docs/PRODUCTION_READINESS_V6.3.md`
- `docs/DEPLOY_DOCKER_V6.3.md`
- `docs/LGPD_SEGURANCA_V6.3.md`
- `docs/E2E_MYSQL_V6.3.md`
- `docs/GEOAPIFY_ADMIN_V6.5.md`
- `docs/RELEASE_NOTES_V6.5.md`
- `docs/VALIDACAO_V6.4.md`

Os documentos antigos permanecem no repositório como histórico das versões anteriores.
