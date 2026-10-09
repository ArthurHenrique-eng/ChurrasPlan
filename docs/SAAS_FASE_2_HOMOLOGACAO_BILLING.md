# ChurrasPlan — Fase 2: Stripe Sandbox B2C/B2B

Branch: Saas-ChurrasPlan. Escopo: contratos e gerenciamento de assinaturas exclusivamente Stripe Test. Não foram consultados nem modificados produtos da conta live, e o backend segue recusando sk_live_.

## 1. Valores comerciais

| Público | Plano técnico | Mensal aprovado | Variável Price ID | Variável valor esperado |
|---|---|---:|---|---|
| B2C | premium | R$ 9,90 | STRIPE_PRICE_USER_PREMIUM_MONTHLY | STRIPE_EXPECTED_PREMIUM_MONTHLY_CENTS=990 |
| B2B | pro (Básico) | R$ 49,90 | STRIPE_PRICE_PRO | STRIPE_EXPECTED_PRO_MONTHLY_CENTS=4990 |
| B2B | business (Pro) | R$ 99,90 | STRIPE_PRICE_BUSINESS | STRIPE_EXPECTED_BUSINESS_MONTHLY_CENTS=9990 |

No Sandbox havia preços divergentes: Premium R$49,90, Pro R$9,90, Business R$139,99. É obrigatório identificar e ajustar as Price IDs no Stripe Test e atualizar o .env local. Uma ID prod_ é produto, não Price ID.

Guardas no backend: preço recorrente ativo, BRL, intervalo e unit_amount esperado, modo test (livemode != true) e IDs diferentes entre todos os planos. Mismatch devolve HTTP 503 antes da criação do Checkout. Valores esperados não vêm do navegador.

Planos anuais NÃO estão homologados comercialmente: STRIPE_EXPECTED_PREMIUM_YEARLY_CENTS=0, STRIPE_EXPECTED_PRO_YEARLY_CENTS=0 e STRIPE_EXPECTED_BUSINESS_YEARLY_CENTS=0 desativam sua oferta. Após aprovação de preços anuais, configurar o valor em centavos e a Price ID correspondente no .env; validar intervalo year, BRL, ativo, test.

## 2. Retorno após autenticação/pagamento

- Checkout Premium pessoal: /minha-conta.html?assinatura=retorno.
- Checkout mercados Pro/Business: /minha-conta.html?cobranca=retorno&organizacao_id=ID.
- Portais do Stripe Test de B2C e B2B voltam a Minha Conta.
- Se a sessão local expirou, a página envia ao login preservando query string, e após autenticação retorna a Minha Conta.
- Na reconciliação B2B de webhook tardio, backend verifica proprietário, tentativa local, checkout.session.status=complete, payment_status=paid, client_reference_id, metadata de organização/plano/período e snapshot da assinatura Stripe com Price ID autorizado. Somente um redirect nunca ativa benefícios.
- Sessões de Checkout abertas antes do commit ainda têm a antiga success_url; testar com nova sessão.

## 3. Ciclo de vida

| Cenário | B2C | B2B |
|---|---|---|
| invoice.paid / renovação | reconciliação Stripe, Premium apenas active com período vigente | reconciliação; Pro/Business active com período |
| invoice.payment_failed e past_due | benefícios Premium suspensos | tolerância BILLING_GRACE_DAYS, máximo 7 dias; replay não prorroga |
| unpaid / canceled | sem benefício | sem benefício |
| cancelar fim do período | POST /api/billing/usuario/cancelar | POST /api/billing/cancelar |
| reativar antes do fim | POST /api/billing/usuario/reativar | POST /api/billing/reativar |
| trocar plano/período | POST /api/billing/usuario/trocar-periodo | POST /api/billing/trocar-plano |
| histórico de faturas | GET /api/billing/usuario/faturas | GET /api/billing/faturas |
| portal | POST /api/billing/usuario/portal | POST /api/billing/portal |
| sincronizar | POST /api/billing/usuario/sincronizar | POST /api/billing/sincronizar |

A troca usa payment_behavior=pending_if_incomplete e proration_behavior=always_invoice. As faturas são filtradas por Customer Stripe da conta ou organização. Rotas de mutação exigem CSRF e titularidade. Webhooks exigem assinatura HMAC, têm deduplicação e consultam sempre o snapshot atual da assinatura.

## 4. Regressões automatizadas

- tests/test_billing_usuario_stripe.py: checkout, webhook HMAC, idempotência, sessão, titularidade, portal e sincronização.
- tests/test_billing_saas.py: RBAC, faturamento por organização, tolerância limitada, troca e cancelamento.
- tests/test_billing_fase2.py: preços divergentes/duplicados/live; retorno pago e não pago; renovação, inadimplência, cancelamento, reativação, troca, faturas e tentativas de IDOR.
- Pipeline da branch: SQLite; MySQL real e Alembic; frontend; segurança; Docker; E2E Chromium; CodeQL. Evidências do CI final serão registradas no roadmap.

Os testes usam transporte simulado Stripe Test, sem requisições reais de cobrança.

## 5. Homologação manual do Sandbox

1. Confira produtos e Price IDs no Stripe Dashboard em TEST, com valores mensais da matriz; não compartilhe chaves ou webhooks.
2. Rode MySQL e alembic upgrade head. Sem Docker, configure PUBLIC_APP_URL=http://127.0.0.1:5500, CORS para porta 5500, API em 8000 e FrontEnd na 5500. Com Docker, use PUBLIC_APP_URL=http://localhost:8080.
3. Execute a Stripe CLI Test com forward-to http://127.0.0.1:8000/api/billing/webhook (sem Docker), ou http://localhost:8080/api/billing/webhook (Docker), e coloque o whsec_ correspondente apenas no .env. Reinicie o backend após alterar.
4. Abra um Checkout Premium NOVO com cartão de teste. Confira retorno direto a Minha Conta, direitos Premium, status, faturas e portal.
5. Use organização nova de mercado com proprietário para testar Pro e Business com Checkout pago; confirme retorno a Minha Conta, vínculo da organização, tenant correto e limites.
6. Verifique cancelamento agendado, reativação, mudança de período homologado e retorno do portal.
7. Para renovação/falhas de pagamento, use cenários controlados do Sandbox / Test Clocks quando aplicável; confirme active/past_due/unpaid/canceled, replays e eventos fora de ordem.
8. Faça login expirado durante o Checkout e tente sincronizar outra organização para confirmar que a autenticação continua obrigatória.

## 6. Limites e pendências

A conta Stripe conectada nesta sessão apareceu somente em modo live; não foi utilizada. Não se considera homologado um pagamento Sandbox real nesta execução. Valores anuais dependem de aprovação, a produção segue desabilitada, e obrigações fiscais/NFS-e, Connect, chargebacks reais, carga e staging permanecem para outras fases. Próxima etapa do Prompt Mestre v2: completar experiência operacional dos parceiros B2B, catálogo, filiais, ofertas e indicadores.
