# Instalação e deploy — ChurrasPlan v3.0

Este documento cobre o caminho recomendado para desenvolvimento e publicação. O Alembic é a fonte de verdade do schema.

## 1. Requisitos

- Python 3.11 ou superior;
- MySQL 8 ou superior;
- servidor/reverse proxy com HTTPS em produção;
- serviço SMTP/transacional se a verificação de e-mail estiver habilitada;
- Google Cloud opcional para Maps/Places.

## 2. Banco de dados

Crie apenas o banco vazio:

```sql
CREATE DATABASE churrasplan
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

Configure `.env` e execute:

```bash
cd BackEnd/Python
alembic upgrade head
```

Verifique:

```bash
alembic current
alembic check
```

O `head` esperado desta release é `20260918_0004`.

`sql/schema.sql` serve como referência/instalação manual limpa. Não aplique o schema manual por cima de um banco versionado pelo Alembic.

## 3. Configuração de desenvolvimento

Exemplo mínimo:

```env
APP_ENV=development
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=sua_senha
DB_NAME=churrasplan
AUTO_CREATE_SCHEMA=false
CORS_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
COOKIE_SECURE=false
REQUIRE_EMAIL_VERIFICATION=false
PUBLIC_APP_URL=http://127.0.0.1:5500
GOOGLE_PLACES_ENABLED=false
```

`AUTO_CREATE_SCHEMA` deve permanecer `false` quando você estiver usando Alembic.

## 4. Configuração de produção

Exemplo conceitual:

```env
APP_ENV=production
DATABASE_URL=mysql+pymysql://usuario:senha@mysql:3306/churrasplan?charset=utf8mb4
AUTO_CREATE_SCHEMA=false
CORS_ORIGINS=https://www.seudominio.com
PUBLIC_APP_URL=https://www.seudominio.com
COOKIE_SECURE=true
REQUIRE_EMAIL_VERIFICATION=true

SMTP_HOST=smtp.seuprovedor.com
SMTP_PORT=587
SMTP_USER=usuario
SMTP_PASSWORD=segredo
SMTP_FROM=ChurrasPlan <no-reply@seudominio.com>
SMTP_TLS=true

GOOGLE_PLACES_ENABLED=true
GOOGLE_PLACES_API_KEY=chave_servidor_restrita
GOOGLE_MAPS_JS_API_KEY=chave_browser_restrita
```

Nunca versione `.env`, senhas ou chaves reais.

A inicialização do backend bloqueia configurações de produção perigosas como cookie sem `Secure`, URL pública sem HTTPS, CORS curinga com credenciais e verificação obrigatória sem SMTP.

## 5. Backend

Instale:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

Execute atrás de um process manager/serviço apropriado. Exemplo simples:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

Em produção, o processo deve ser supervisionado pelo seu ambiente (systemd, container/orquestrador ou plataforma PaaS).

## 6. Frontend e reverse proxy

O frontend é estático. Sirva `FrontEnd/` por Nginx/CDN/host estático.

Recomendação: publicar frontend e API no mesmo domínio e encaminhar `/api` ao FastAPI. Isso reduz complexidade de CORS/cookies.

Fluxo recomendado:

```text
https://www.seudominio.com/*     -> FrontEnd estático
https://www.seudominio.com/api/* -> FastAPI:8000
```

Quando frontend e API estiverem em domínios diferentes, configure explicitamente `CORS_ORIGINS` e a URL da API no frontend. Teste cuidadosamente cookies `SameSite`, HTTPS e CSRF.

## 7. E-mail

Em produção, recomenda-se `REQUIRE_EMAIL_VERIFICATION=true`.

Sem SMTP configurado, a aplicação recusa iniciar em produção quando essa opção estiver ligada. Em desenvolvimento, tokens podem ser retornados de forma controlada para testes; isso não deve ser usado como fluxo de produção.

## 8. Google Maps e Places

O mapa é opcional. Sem chave, a área de comparação continua capaz de trabalhar com estabelecimentos próprios que possuam coordenadas.

Use duas chaves quando possível:

- servidor: Places API, restrita às APIs necessárias e à infraestrutura;
- navegador: Maps JavaScript API, restrita aos domínios autorizados.

Não coloque chaves irrestritas no código-fonte.

## 9. Parceiros e ofertas

Um usuário pode ativar perfil de parceiro e cadastrar estabelecimento/produto/oferta. Por segurança de produto, ofertas de estabelecimento ainda não verificado não entram nas recomendações públicas.

A aprovação é uma ação administrativa. Antes de produção, defina um processo operacional de verificação de parceiros.

## 10. Dados demonstrativos

`sql/seed_data.sql` pode preencher catálogo e algumas ofertas de demonstração. Elas não são preços reais e não devem ser apresentadas ao usuário final como informação comercial atual.

Em produção, escolha conscientemente se deseja executar o seed. O ideal é carregar apenas catálogo genérico e administrar ofertas reais por fonte confiável.

## 11. Migração de banco existente

Antes de atualizar:

1. backup lógico e, se disponível, snapshot do banco;
2. restaure o backup em staging;
3. execute `alembic upgrade head` em staging;
4. execute testes/smoke tests;
5. somente então atualize produção.

A v3 preserva dados do schema anterior e faz backfill dos novos campos compatíveis. Histórico legado de preço que não tinha unidade comercial confiável continua tratado conservadoramente.

## 12. Checklist antes de publicar

- [ ] DNS configurado;
- [ ] HTTPS válido;
- [ ] `APP_ENV=production`;
- [ ] MySQL com backup automatizado;
- [ ] `alembic current` no head;
- [ ] `COOKIE_SECURE=true`;
- [ ] CORS apenas para domínios conhecidos;
- [ ] SMTP real testado;
- [ ] verificação e recuperação de e-mail testadas;
- [ ] chaves Google restritas;
- [ ] contas administrativas protegidas;
- [ ] fluxo de aprovação de parceiros definido;
- [ ] logs/monitoramento configurados;
- [ ] política de privacidade/termos/cookies atualizados;
- [ ] rotina de backup e restauração testada;
- [ ] `pytest -q` verde;
- [ ] smoke test no ambiente final.

## 13. O que ainda não está conectado

A estrutura de planos/assinaturas existe, porém a v3.0 não possui gateway de cobrança. Escolha Stripe, Mercado Pago ou outro provedor em uma fase posterior e implemente webhooks/idempotência antes de ativar assinaturas pagas.
