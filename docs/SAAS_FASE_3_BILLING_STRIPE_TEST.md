# Fase 3 — Billing SaaS B2B (Stripe Test; sem ativar cobrança real)

**Branch:** `Saas-ChurrasPlan`. **Migration:** `20261008_0014` (após `0013`). Fluxo implementado no backend e painel de parceiros. Esta entrega **não prova transação com conta Stripe real, nem habilita produção**. Falta criar preços recorrentes BRL no dashboard Stripe, configurar segredos de TEST, configurar webhook e homologar manualmente; sem isso, o sistema responde HTTP 503 para operações financeiras e mantém os tenants em Free/cortesia.

## Arquitetura / dados

- `assinaturas_organizacao`: no máximo uma assinatura Stripe por organização, com `stripe_subscription_id`, `stripe_customer_id`, tier reconciliado, status, fim do período, tolerância e cancelamento ao término. **Não é** a tabela legada `assinaturas_usuario` de B2C.
- `tentativas_checkout`: checkout iniciado pelo proprietário, chave idempotente exclusiva por organização, vínculo org/usuário/plano/sessão Stripe. Nenhuma sessão é tomada como pagamento concluído.
- `eventos_billing`: log de **IDs únicos de evento** e resultado; não guarda dados de cartão nem corpo integral do evento.
- Concessões administrativas continuam separadas. `services.entitlements.resolver_plano` usa assinatura reconciliada **ativa e não expirada** como prioridade; em seguida concessão administrativa vigente; senão Free. O frontend não pode escrever o tier.
- Cota Free/Pro/Business já existente e cota de membros seguem de acordo com `resolver_plano`. Downgrade após expiração/desativação preserva cadastros, mas bloqueia **novas inclusões** excedentes.
- **Preço não inventado:** códigos `STRIPE_PRICE_PRO`/`STRIPE_PRICE_BUSINESS` apontam para Prices **ativos, recorrentes mensais e BRL**, e o backend consulta o Stripe Test para conferir moeda, periodicidade e valor real (centavos).

## Configuração, necessária para testar no sandbox oficial

1. Criar conta Stripe com sandbox/test mode, cadastrar produtos `Pro` e `Business` com recorrência **mensal** em **BRL**. Copiar os IDs `price_...`. Nenhum valor foi atribuído automaticamente.
2. Gerar a **secret key de TEST** (prefixo `sk_test_`). Não usar `sk_live_`, chaves de produção, dados de cartão real, ou vazar segredo no GitHub, JavaScript, logs ou README.
3. Registrar endpoint HTTPS de webhook da API em `POST /api/billing/webhook`, com eventos `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `customer.subscription.paused`, `customer.subscription.resumed`, `invoice.paid`, `invoice.payment_failed`, `invoice.marked_uncollectible`. Copiar secret de assinatura de TEST `whsec_...`.
4. Configurar **exclusivamente no ambiente secreto do servidor**: `BILLING_ENABLED=true`, `STRIPE_SECRET_KEY=sk_test_...`, `STRIPE_WEBHOOK_SECRET=whsec_...`, `STRIPE_PRICE_PRO=price_...`, `STRIPE_PRICE_BUSINESS=price_...`, `PUBLIC_APP_URL=https://seu-dominio...`, `BILLING_GRACE_DAYS=3`. Padrão de todas as configurações: **desligado**.
5. Se desejar alterar forma de pagamento via painel, habilitar Stripe **Customer Portal** em test mode; sem isso o provedor poderá recusar `/api/billing/portal`. As credenciais não são configuradas pela IA nem estão armazenadas no repositório.
6. Rodar `alembic upgrade head`, conferir `/api/health/ready` e testar compra simulada, falha, renovação, atualização e cancelamento com **test cards oficiais** e Stripe CLI. Validar retorno ao painel e atualização do banco após webhook.
7. **Pagamentos reais não estão disponíveis por projeto**: `billing_habilitado` rejeita qualquer chave sem prefixo `sk_test_`. Mesmo em `APP_ENV=production`, a integração atual só roda Stripe Test. Para operação real será necessário projeto separado com habilitação explícita, impostos/documentação fiscal, compliance, reembolsos, conciliação e aprovação humana.

## Endpoints

| Método | Rota | Autorização |
| --- | --- | --- |
| GET | `/api/billing/assinatura` | Proprietário local da organização |
| GET | `/api/billing/catalogo` | Proprietário local; consulta Prices Stripe Test |
| GET | `/api/billing/faturas` | Proprietário local; últimas 20 faturas Stripe Test do customer |
| POST | `/api/billing/checkout` | Proprietário + CSRF; plano Pro/Business e chave idempotente |
| POST | `/api/billing/trocar-plano` | Proprietário + CSRF; substituição de Price via Stripe com `pending_if_incomplete` |
| POST | `/api/billing/cancelar` | Proprietário + CSRF; `cancel_at_period_end=true` |
| POST | `/api/billing/sincronizar` | Proprietário + CSRF; consulta estado atual Stripe e atualiza banco |
| POST | `/api/billing/portal` | Proprietário + CSRF; redirecionamento seguro ao portal |
| POST | `/api/billing/webhook` | Público **apenas para Stripe**; corpo assinado por HMAC SHA-256 com janela de 5 minutos |

No checkout, a identidade do usuário e organização é verificada em membership (inclusive para conta global `admin`); gestor/editor/leitor não contratam nem visualizam o faturamento da empresa. O plano é escolhido de um enum permitido, e o preço vem **somente** da configuração do backend validada no Stripe.

Eventos duplicados são tratados por `event_id`; a reconciliação faz **GET do estado corrente da assinatura no Stripe**, evitando que webhooks entregues fora de ordem reinstalem status anteriores. Webhooks de assinatura com preço estranho, organização incorreta, checkout não vinculado, assinatura inválida ou assinatura criptográfica inválida **não liberam benefícios**. Ao trocar o plano, o Price efetivo do item retornado pelo Stripe determina o tier; atualização pendente sem pagamento não o altera.

## Estados operacionais

- `active`: Pro/Business liberado **até o fim do período corrente retornado no Stripe**; término é lido de `items.data.current_period_end` (compatível com Stripe Basil e posterior).
- `past_due`: tolerância limitada, configurada em dias (0–7; padrão 3); reenvio de evento não reinicia prazo. Ao expirar, volta para o tier Free ou cortesia administrativa.
- `incomplete`, `unpaid`, `paused`, `canceled`, `incomplete_expired`: sem benefícios pagos. `trialing` não ativa tier pago automaticamente; trials dependem de política explícita futura.
- `cancel_at_period_end=true`: preserva benefício ativo até o fim do período pago, depois desativa no relógio local, mesmo sem job programado.
- Renovação `invoice.paid` / `customer.subscription.updated`: a API obtém estado e período atual do Stripe; não soma dias nem calcula valores por conta própria.
- `POST /sincronizar`: recuperação manual do estado atual; webhooks permanecem fonte normal do fluxo automático. Reembolsos e disputas precisam de conferência no Stripe Dashboard e política financeira específica; **não declarar estorno automatizado**.

## Testes e gates

- SQLite: ausência de credenciais bloqueia checkout, usuário não pode promover o próprio tier, CSRF, vínculo org/proprietário, chave de idempotência, signature HMAC/timestamp, replay, checkout incompleto, confirmação de assinatura, expiração, past_due, downgrade, restauração e eventos fora de ordem.
- MySQL/Alembic: `upgrade head`, paridade de `schema.sql` e ORM, `alembic check`, downgrade/upgrade preservando legado e corrida real para a mesma tentativa de checkout.
- Frontend: renderiza somente Price do Stripe Test; autorização de escrita fica no backend, links do provedor são limitados a domínios Stripe HTTPS. E2E Chromium existente confirma regressões; **não equivale a checkout integrado a uma conta Stripe verdadeira**.
- CodeQL: Python + JavaScript. Não considerar homologação financeira de produção apenas com mocks/CI.

## Rollback/privacidade e implantação

- Antes de qualquer downgrade de `0014`, salvar as tabelas de assinaturas, tentativas e eventos; **rollback destrói o histórico de cobranças locais, mas não cancela assinaturas no Stripe**. Nunca executar rollback de Billing ativo sem suspensão de vendas e reconciliação externa.
- Stripe mantém os dados sensíveis de cartão; a API nunca recebe PAN/CVV. Persistimos apenas IDs Stripe, status, data de término e IDs de auditoria. Avaliar políticas de retenção LGPD e processo de direitos de titular.
- Regras jurídicas, fiscais, política de reembolso, contabilidade, operação de chargebacks, DNS/TLS, backups, alertas de webhook e rollout gradual ainda exigem validação humana e infraestrutura de produção.

Fontes de contrato Stripe: [Checkout Sessions](https://docs.stripe.com/api/checkout/sessions), [Subscriptions Update](https://docs.stripe.com/api/subscriptions/update), [Stripe Events](https://docs.stripe.com/api/events) e [Subscription Billing Periods](https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end).
