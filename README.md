# ChurrasPlan v6.5.0 — Geoapify + administração segura

<p align="center">
  <img src="docs/assets/LogoChurrasPlan.png" alt="Ícone do ChurrasPlan" width="72" />
  &nbsp;&nbsp;&nbsp;
  <img src="docs/assets/LogoTXTChurrasPlan.png" alt="ChurrasPlan" width="230" />
</p>

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

A trilha SaaS introduz organizações com papéis locais e isolamento B2B inicial. Consultas do painel usam a organização do membro; para usuários em mais de uma organização, o cabeçalho `X-Organizacao-ID` é obrigatório. **Entitlements, convites e seletor multi-org estão implementados; cobrança real continua desativada.** Veja `docs/SAAS_FASE_2A_ORGANIZACOES.md` e `docs/SAAS_FASE_2D_OPERACAO_B2B.md` para a operação atual.

- produto genérico + SKU comercial;
- catálogo genérico amplo por categoria para parceiros: carnes, bebidas, mercearia, laticínios, padaria, hortifruti, congelados, limpeza, higiene e descartáveis;
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
├── docker-compose.dev.yml
├── docker-compose.prod.yml  # override sobre dev; não é a stack independente
└── docker-compose.production.yml  # stack HTTPS/Caddy independente
```

## Banco e Alembic

O Alembic é a fonte de verdade da evolução do banco.

Head atual:

```text
20261008_0014
```

Cadeia:

```text
20260917_0001  baseline consistente
20260918_0002  contas/orçamento/RSVP/SKUs/parceiros
20260918_0003  alinhamentos de schema
20260918_0004  métricas agregadas de estabelecimentos
20260918_0005  LGPD, rate limiting e auditoria admin
20260922_0006  restaura defaults de timestamps em usuarios
20260925_0007  amplia catálogo genérico para cadastro de produtos de parceiros
20260925_0008  garante catálogo base do planejador em toda instalação
20261008_0009  organizações B2B, membros e backfill conservador de parceiros
20261008_0010  concessões administrativas temporárias e limites B2B (sem billing)
20261008_0011  convites B2B, equipes, auditoria e gestão de membros
20261008_0012  filiais com código/matriz e lotes de ofertas CSV idempotentes
20261008_0013  importação em massa de SKUs e campanhas comerciais moderadas
20261008_0014  assinaturas B2B, checkout Stripe Test, webhooks e histórico de cobrança

A Fase 2C permite convidar equipes, revogar membros, aplicar papéis por organização e alternar entre contas no painel. Segurança, fluxos, migração/rollback e cotas: `docs/SAAS_FASE_2C_MEMBROS_CONVITES.md`. **Checkout e assinaturas estão implementados somente para Stripe Test, desligados por padrão.**

O painel de parceiros aplica cotas B2B transacionais. Organizações começam sempre no tier Free; concessões temporárias Pro/Business dependem de administrador global, CSRF e registro de auditoria. **Checkout Stripe Test só fica disponível após configuração explícita; pagamentos reais continuam desativados.** Contratos, limites e rollback: `docs/SAAS_FASE_2B_ENTITLEMENTS.md`.
```

`BackEnd/Python/sql/schema.sql` representa uma **instalação nova** no head atual. Para banco existente, use migrations.

## Rodar com Docker — desenvolvimento

Pré-requisito: Docker + Docker Compose.

```bash
cp .env.docker.example .env
docker compose -f docker-compose.dev.yml up --build
```

Abra:

```text
http://localhost:8080
```

Swagger:

```text
http://localhost:8080/docs
```

A stack sobe MySQL 8.4, aplica migrations, garante o catálogo genérico e carrega registros de **referência de planejamento** em desenvolvimento, inicia FastAPI e serve o frontend via Nginx.

Os preços de desenvolvimento existem somente para exercitar orçamento, custo por pessoa e divisão. Para desabilitá-los:

```bash
LOAD_DEMO_DATA=false docker compose -f docker-compose.dev.yml up --build
```

Os valores de referência servem para estimativa de orçamento. Eles não são ofertas comerciais nem preços garantidos; ofertas reais cadastradas e verificadas sempre têm prioridade no cálculo.

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

Na trilha SaaS, a branch `Saas-ChurrasPlan` também executa os seis jobs em pushes, além de PRs. A configuração de `CodeQL` faz análise estática de Python e JavaScript; o `Dependabot` propõe atualizações de dependências via PRs direcionados à branch SaaS. As regras de proteção e aprovações obrigatórias ainda devem ser configuradas no GitHub conforme `docs/SAAS_FASE_1C_SEGURANCA_INFRA.md`.

A etapa de **deploy** não está ligada a um provedor específico. Isso é intencional: primeiro deve ser definido onde staging/produção serão hospedados e como os segredos serão gerenciados.

## Produção com Docker + HTTPS

A composição recomendada é a independente:

```bash
cp .env.production.example .env.production
# preencha domínio, SMTP e segredos reais em .env.production (não comite este arquivo)
chmod 600 .env.production
# --env-file é obrigatório: Compose NÃO carrega .env.production por padrão
docker compose --env-file .env.production -f docker-compose.production.yml config --quiet
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
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

A v6.5 usa Geoapify para mapa, busca de estabelecimentos próximos e autocomplete de endereços. Uma única chave fica somente no backend:

```dotenv
GEOAPIFY_ENABLED=true
GEOAPIFY_SERVER_API_KEY=chave_restrita_ao_backend
```

O frontend não recebe a chave Geoapify. Os Map Tiles são carregados por um endpoint autenticado do próprio ChurrasPlan, que encaminha a requisição à Geoapify e permite cache HTTP no navegador. Isso evita problemas de restrição por referrer/origin e reduz exposição de credenciais.

Fluxo implementado: usuário autenticado abre **Onde comprar** → usa geolocalização ou digita um endereço → o backend consulta Address Autocomplete/Places da Geoapify → o frontend desenha o mapa com MapLibre GL e Map Tiles Geoapify entregues pelo backend → ao arrastar ou alterar o zoom, novos pontos são consultados para a área visível → a lista lateral continua representando os estabelecimentos próximos da localização original → a otimização da cesta continua usando somente ofertas/preços próprios do ChurrasPlan.

Sem a chave de servidor, a página continua funcional com os estabelecimentos cadastrados e a otimização própria; mapa, autocomplete e busca externa ficam desativados de forma graciosa.

## Integrações externas restantes

Ainda exigem credenciais reais:
- SMTP para verificação/reset de e-mail;
- Geoapify conforme configuração acima;
- eventual provedor de pagamento, ainda não conectado.

Preços de referência do planejador são **estimativas nacionais de orçamento**, não ofertas comerciais nem preços garantidos. Quando há oferta real/verificada para um item, ela substitui a referência no cálculo.

## Documentação desta etapa

- `docs/PRODUCTION_READINESS_V6.3.md`
- `docs/DEPLOY_DOCKER_V6.3.md`
- `docs/LGPD_SEGURANCA_V6.3.md`
- `docs/E2E_MYSQL_V6.3.md`
- `docs/GEOAPIFY_ADMIN_V6.5.md`
- `docs/RELEASE_NOTES_V6.5.md`
- `docs/VALIDACAO_V6.4.md`

Os documentos antigos permanecem no repositório como histórico das versões anteriores.

### Fase 4A — Catálogo e campanhas B2B

Importação CSV de produtos comerciais com criação/atualização por SKU, verificação de EAN, cotas e repetição idempotente; campanhas associadas a ofertas existentes, submetidas à revisão de administrador e exibidas publicamente só após aprovação e dentro da vigência. Consulte `docs/SAAS_FASE_4A_CATALOGO_CAMPANHAS.md`. **Pagamentos reais permanecem desativados; o sandbox Stripe Test é configurável pela Fase 3.**

### Fase 3 — Billing B2B (somente sandbox)

Assinaturas por organização com tiers Free/Pro/Business, checkout Stripe Test, webhook HMAC, controle de assinatura, renovação, inadimplência/tolerância, cancelamento, conciliação, troca de plano e histórico de faturas de teste. Consulte `docs/SAAS_FASE_3_BILLING_STRIPE_TEST.md` e configure Prices e credenciais Stripe Test **fora do repositório**. O sistema recusa chaves `sk_live_` e não disponibiliza cobrança em produção.
