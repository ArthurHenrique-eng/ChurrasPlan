# Stripe TEST — assinaturas pessoais e comerciais (SaaS-ChurrasPlan)

**Escopo:** pagamentos de assinatura SaaS apenas em sandbox Stripe. Não há cobrança real, Stripe Connect nem split de pagamentos. O catálogo de produtos do churrasco **não** é catálogo de produtos Stripe.

## Acesso dos clientes
- Abra `FrontEnd/planos.html` ou clique em **Planos** na página inicial.
- Consumidor: clique em **Assinar Premium**. Se não estiver autenticado, faça cadastro/login e retorne à seleção; então confirme o Checkout Stripe Test.
- Mercado: clique em **Assinar Mercado Pro** ou **Business**. A conta pode ser ativada como parceira, com uma organização inicial gratuita. Só o **proprietário** pode contratar; quando há múltiplas organizações, o usuário seleciona a correta no painel `parceiro.html`, na seção Assinatura comercial.
- A conclusão do Checkout **não ativa** recursos pagos no navegador. O webhook assinado reconcilia com o estado atual do Stripe e atualiza o banco. O portal de gerenciamento fica em `minha-conta.html` (usuário) ou `parceiro.html` (mercado).
- Acesso premium pessoal e assinatura da organização são registros independentes.

## Setup local (credenciais nunca entram no Git)
1. No **Stripe Test / Sandbox**, crie Prices recorrentes BRL para Premium usuário (mensal, opcional anual) e para Pro/Business mercado (ambos mensais, anuais opcionais).
2. Prepare o arquivo `.env` local a partir de `.env.docker.example` e preencha valores reais **somente de teste**:
```dotenv
BILLING_ENABLED=true
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_USER_PREMIUM_MONTHLY=price_...
STRIPE_PRICE_USER_PREMIUM_YEARLY=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_BUSINESS=price_...
STRIPE_PRICE_PRO_YEARLY=price_...
STRIPE_PRICE_BUSINESS_YEARLY=price_...
```
3. Configure `PUBLIC_APP_URL=http://localhost:8080` para Docker de desenvolvimento; no `docker-compose.dev.yml` este endereço já é atribuído pelo Compose. Execute:
```bash
docker compose -f docker-compose.dev.yml up --build
```
4. Para webhooks locais, use a **Stripe CLI em test mode**, encaminhando para `http://localhost:8080/api/billing/webhook`. Use no `.env` o segredo `whsec_...` apresentado por essa sessão da CLI e reinicie o backend; em ambiente hospedado, configure o endpoint HTTPS no painel do sandbox com eventos: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`, `invoice.marked_uncollectible`.
5. Opcional: ative o **Customer Portal** para o sandbox Stripe e configure alterações e cancelamentos.
6. Em ambiente local, abra `http://localhost:8080/planos.html`. Valores devem vir de `/api/billing/usuario/catalogo` e `/api/billing/planos-publicos`. IDs ausentes deixam botões desativados; **não são mostrados preços fictícios**.
7. Use cartões de teste oficiais Stripe e a Stripe CLI para simular sucesso, falha e cancelamento. Não compartilhe `sk_test_`, `whsec_` ou `sk_live_` com assistentes ou em commits.

## API
| Endpoint | Objetivo |
| --- | --- |
| `GET /api/billing/usuario/catalogo` | Prices Premium públicos de teste |
| `POST /api/billing/usuario/checkout` | Checkout Premium; sessão e CSRF |
| `GET /api/billing/usuario/assinatura` | Status da assinatura do usuário |
| `POST /api/billing/usuario/portal` | Gerenciamento Premium; sessão e CSRF |
| `GET /api/billing/planos-publicos` | Prices de mercados para vitrine |
| `POST /api/billing/checkout` | Checkout de mercado mensal/anual, membro proprietário + CSRF |
| `POST /api/billing/portal` | Portal da organização; proprietário + CSRF |
| `POST /api/billing/webhook` | Recebe webhooks assinados dos dois públicos |

O backend valida os Price IDs na Stripe e usa metadados de titularidade apenas com tentativas de checkout locais. Webhooks repetidos são deduplicados por ID e assinaturas são reconciliadas com snapshot atual do Stripe. O status `active` e período não expirado habilitam Premium; eventos `past_due`, `unpaid` e `canceled` não habilitam Premium. Regras antigas de Pro/Business B2B preservam grace period separado.

## Entrega e limites
- Migrations Alembic: `20261008_0015` e `20261008_0016` (após `0014`).
- `sql/schema.sql` atualizado como referência de nova instalação. Para bancos existentes use **`alembic upgrade head`**, nunca recrie tabelas.
- O fluxo Premium autoriza o pagamento e expõe status no perfil, mas os recursos Premium específicos ainda precisam ser definidos e aplicados por endpoint. Não considerar uma funcionalidade comercial liberada apenas pelo texto da UI.
- **Não houve homologação com uma conta Stripe real/teste via rede externa nem deploy nesta mudança.** As credenciais privadas do sandbox não são lidas pelo GitHub.
- Stripe Invoicing não equivale a documento fiscal brasileiro; Tax/NFS-e e cobrança live exigem implantação e validação à parte.

## Diagnóstico da página de planos

A criação dos produtos e preços no Dashboard Stripe **não** configura o backend
automaticamente. O `docker-compose.dev.yml` só repassa as variáveis definidas
no `.env` local. Sem `BILLING_ENABLED=true`, `sk_test_`, `whsec_`
ou Price IDs ativos correspondentes, os botões permanecem bloqueados
por segurança.

Se o catálogo do Stripe tiver os produtos **ChurrasPlan Premium (R$ 9,90/mês)**,
**Parceiro Básico (R$ 49,90/mês)** e **Parceiro Pro (R$ 99,90/mês)**,
a associação esperada no site é:

| Produto criado no Stripe Sandbox | Plano da vitrine | Variável |
| --- | --- | --- |
| ChurrasPlan Premium mensal | Premium | `STRIPE_PRICE_USER_PREMIUM_MONTHLY` |
| Parceiro Básico mensal | Pro (mercado) | `STRIPE_PRICE_PRO` |
| Parceiro Pro mensal | Business (mercado) | `STRIPE_PRICE_BUSINESS` |

Os três valores acima são exemplos vistos no ambiente de desenvolvimento,
não preços fixos no frontend. Os anuais permanecem opcionais: configure
`STRIPE_PRICE_USER_PREMIUM_YEARLY`, `STRIPE_PRICE_PRO_YEARLY`
e `STRIPE_PRICE_BUSINESS_YEARLY` somente quando existirem Prices anuais.

Copie cada **ID do preço** (prefixo `price_`, não `prod_`) diretamente
do sandbox correto em Catálogo de produtos → Produto → Preços. Use uma
`STRIPE_SECRET_KEY` `sk_test_` da **mesma área restrita**. Não compartilhe
segredos ou comite `.env`.

Para verificar se os containers receberam a configuração sem revelar segredos,
execute no PowerShell:

```powershell
docker compose -f docker-compose.dev.yml exec backend python -c "import os; names=['BILLING_ENABLED','STRIPE_SECRET_KEY','STRIPE_WEBHOOK_SECRET','STRIPE_PRICE_USER_PREMIUM_MONTHLY','STRIPE_PRICE_PRO','STRIPE_PRICE_BUSINESS']; [print(n, 'CONFIGURADO' if os.getenv(n) else 'AUSENTE') for n in names]"
```

Depois de salvar `.env`, recrie o serviço para reaplicar as variáveis
de ambiente (sem apagar os volumes):

```powershell
docker compose -f docker-compose.dev.yml up -d --build --force-recreate
curl.exe -i http://localhost:8080/api/billing/usuario/catalogo
curl.exe -i http://localhost:8080/api/billing/planos-publicos
```

Os dois endpoints devem retornar `planos` com os preços configurados e
validados. Se houver 502/503, confira os logs do backend e se a chave e
os Prices pertencem à mesma área restrita:

```powershell
docker compose -f docker-compose.dev.yml logs --tail=80 backend
```

A logo da página `planos.html` agora tem tamanhos limitados localmente em
`css/planos.css`, independentemente dos estilos da home. O PWA deve buscar
o CSS atualizado; em caso de cache antigo, limpe o Service Worker e recarregue.
