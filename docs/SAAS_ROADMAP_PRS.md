# Roadmap SaaS — PR por fase, gates de qualidade

Branch de trabalho **exclusiva** definida pelo mantenedor: `Saas-ChurrasPlan` (nunca `main`). **Não criar outras branches de fase.** Commits de incremento devem ocorrer diretamente nesta branch, com verificações de cada commit final por GitHub Actions (CI e CodeQL), documentação e ausência de falhas antes de marcar a entrega como concluída. Os PRs #3 a #8 pertencem ao histórico já consolidado.

| Ordem | Fase | Incremento principal | Gate verificável |
| --- | --- | --- | --- |
| 0 | Auditoria | Diagnóstico 30 frentes, evidência de baseline e dependências | PR documentado, checks GitHub verdes, revisão |
| 1 | Estabilidade P0 | Cadastro de lojas (coordenadas), seletor de genéricos, preços; correção README/Compose; reforço segurança, CI/CSP, MFA, observabilidade, backup/restore | Tests SQLite + MySQL/Alembic + Playwright parceiro/admin + security + build/compose; qualquer restore real comprovado ou bloqueado |
| 2 | SaaS Core | Organização/membros/papéis/filiais, migração de parceiros, isolamento multi-tenant e entitlements | MySQL migration forward/backward/dados preservados; testes cross-tenant e concorrência de limites; E2E |
| 3 | Billing | Planos, provedor sandbox, checkout, webhook, renovação, reembolso quando aplicável, grace/downgrade/cancelamento | Testes de assinaturas, falha, replay, idempotência, out-of-order, reconciliação; **nada ativa pago a partir do frontend** |
| 4 | Operação B2B | Catálogo/importação CSV, campanhas, filiais, onboarding e relatórios comerciais | Testes autorização por org, importações parciais/duplicadas, atualização em massa e métricas não transacionais |
| 5 | Growth/Marketplace | Landing parceiros, captação/CRM, SEO, referral, eventos de produto e dashboard fundador | Testes SEO/privacidade/consentimento; funis com origem e retenção, sem alegar vendas sem provas |
| 6 | IA/automações | AGENTS e revisão, assistente opcional estruturado, limites custos, outbox/fila se necessária | Falha de LLM não quebra cálculo; nenhuma mutação financeira pelo LLM; jobs idempotentes |
| 7 | Piloto/lançamento | Staging, smoke/rollback, carga, restore, suporte, documentação, piloto regional | Relatório com aprovações e bloqueios reais; lançamento só após gates de produto, segurança, billing e operação |

## Regras de cada incremento na Saas-ChurrasPlan

1. Listar escopo, arquivos alterados, migrations e contrato de API; registrar efeitos B2C/B2B/admin. Commit diretamente na branch SaaS conforme instrução do mantenedor, sem ramificações auxiliares.
2. Demonstrar comandos, testes passados/falhos, referências à execução GitHub Actions e limitações de ambiente.
3. Testar no MySQL real quando houver persistência; validar `alembic check`, retenção de dados legados e rollback adequado.
4. Cobrir segurança de rota por backend: CSRF, papéis, isolamento organizacional, rate limit, webhooks autenticados e idempotência conforme escopo.
5. Evidenciar impacto no planejador: regras determinísticas, preços (referência vs oferta), PWA, e fronteiras entre compra física e quantidade comercial.
6. Não esconder falhas de CI nem declarar integrações externas ativas sem sandbox/produção demonstrados.
7. Bloquear conclusão da fase com falhas dos jobs: `Backend unit/integration (SQLite)`, `MySQL 8 real + Alembic`, `Frontend static checks`, `Security audit`, `Docker configuration and images`, `E2E Chromium + MySQL`.
8. Atualizar esse roadmap com o status **somente depois** da prova e revisão. Sem assinatura paga fictícia, sem deploy/push para `main`.

## Dependências arquiteturais

`B2C estável` → `organizações e isolamento` → `entitlements` → `billing sandbox integrado` → `operação B2B escalável` → `funis e valor demonstrável` → `piloto e validação comercial`.

Dependências humanas explícitas: configurar conta real de cobrança, chaves/contratos, DNS e servidores, backups externos, consultoria jurídica/tributária, recrutamento de parceiros e validação de disposição a pagar. Parte técnica pode ser desenvolvida com adapters/mocks/sandbox, sem simular resultado financeiro real.

## Status e próximas lacunas
- **Fases 0, 1A–1C e 2A–2C:** implementadas e comprovadas por CI; ver histórico PR #3 a #8 e documentação de cada etapa.
- **Fase 2D (operação essencial B2B):** filiais via estabelecimentos com código/matriz, CSV de ofertas idempotente, onboarding e métricas agregadas, documentados em `docs/SAAS_FASE_2D_OPERACAO_B2B.md`. Os gates de CI/CodeQL devem corresponder ao commit de entrega.
- **Pendente na operação comercial da Fase 4:** catálogo comercial por CSV, atualização em massa, campanhas com vigência e governança, integrações ERP e análises transacionais com dados reais.
- **Pendente nas Fases 1/3/7:** MFA, observabilidade operacional, backups/restore externo, credenciais e homologação do sandbox Stripe Test, operação de cobranças reais, infraestrutura de staging e homologação para piloto. Não declarar disponibilidade comercial antes dessas validações.

## Fase 4A — Catálogo e campanhas

Incremento realizado diretamente em `Saas-ChurrasPlan`: importação CSV de SKU por organização com upsert e idempotência, campanhas de ofertas próprias com submissão, moderação administrativa, data de início/fim e cancelamento, listagem pública exclusivamente de campanhas elegíveis. Runbook e contratos: `docs/SAAS_FASE_4A_CATALOGO_CAMPANHAS.md`. Ainda faltam campanhas de mídia paga, integração ERP, prova de vendas transacionais, integração de compras reais e homologação externa e configuração operacional do Billing da Fase 3.

## Fase 3 — Billing Stripe Test

Estrutura e fluxos B2B implementados diretamente na branch `Saas-ChurrasPlan`: checkout de assinaturas mensais com Price BRL verificado no Stripe Test, webhook HMAC SHA-256, idempotência, reconciliação com snapshot remoto, proteção de tenant, downgrade, cancelamento, troca de planos e histórico de faturas. Migration `20261008_0014`. Manual: `docs/SAAS_FASE_3_BILLING_STRIPE_TEST.md`. **Gates externos ainda necessários:** configurar conta Stripe Test, Prices e webhook reais no ambiente, homologar transações end-to-end no sandbox. Pagamento em produção e emissões fiscais não foram ativados.

## Fase 1 B2C — Matriz Free/Premium (09/10/2026)

**Autorização do mantenedor:** Free com 5 planejamentos salvos; Premium com
planejamentos ilimitados, comparação avançada, PDF/CSV de planejamento,
modelos de eventos reutilizáveis e análise detalhada de custos.
Incremento entregue **diretamente** em `Saas-ChurrasPlan`; não houve alterações em `main`
ou habilitação de cobranças live.

**Arquitetura de entitlements:** `services/entitlements_usuario.py` usa somente
`assinaturas_stripe_usuario` reconciliada (ativa e no período) como fonte
de direito individual; `usuarios.plano` e `assinaturas_usuario` não concedem
benefícios. O GET `/api/planos/meus-beneficios` expõe quota efetiva, uso e
recursos. Quota transacional Free em criação, repetição e reivindicação de
churrasco; a atualização idempotente de um churrasco existente não consome
uma nova vaga. Registros acima da quota após downgrade permanecem acessíveis.

**Recursos e dados:** análise de custos com qualidade de estimativa e categorias,
comparação de cestas verificadas sem simular vendas, exportações Premium PDF/CSV
(com proteção contra fórmulas), snapshots de modelos pessoais e reaplicação
pelo motor determinístico. Modelo SQL `modelos_evento_usuario`, migration
reversível `20261009_0017`, esquema canônico `sql/schema.sql` atualizado.
Rota LGPD de exportação inclui dados da assinatura Stripe TEST; exclusão
local é bloqueada enquanto a assinatura remota não estiver encerrada.
`minha-conta.html` e `planos.html` apresentam as condições aprovadas.

**Testes/regressões:** suíte `tests/test_entitlements_usuario_fase1.py`
(Free, Premium TEST, limites, histórico preservado, PDF/CSV, IDOR, CSRF,
vencimento, modelos, bloqueio de exclusão com contrato financeiro pendente);
CI existente executa SQLite, MySQL 8 + Alembic upgrade/check/downgrade/upgrade,
estática frontend, auditoria de segurança, builds Docker e Chromium E2E.
Os jobs históricos de alguns commits intermediários falharam em
`requirements.txt` (separador de versão), parity `schema.sql`,
head esperado de migration e rollback de índice sustentando FK MySQL;
essas regressões foram corrigidas incrementalmente. **Somente marcar a Fase 1
como aprovada depois que o CI final e CodeQL do commit final estiverem verdes.**

**Gates confirmados (commit de código `6695c2a91a553c8087bc0b636070aa12538bcc32`):**
[ChurrasPlan CI #38000556036](https://github.com/ArthurHenrique-eng/ChurrasPlan/actions/runs/38000556036)
**success**, seis jobs aprovados, inclusive **161 pytest SQLite aprovados**,
**12 testes MySQL aprovados** (incluindo duas criações simultâneas para uma
vaga Free), `alembic check`, downgrade/upgrade MySQL, frontend static,
auditoria de dependências, build Docker e E2E Chromium + MySQL.
[CodeQL #38000556044](https://github.com/ArthurHenrique-eng/ChurrasPlan/actions/runs/38000556044)
**success**. Esses checks provam regressões e contratos simulados, não homologam
Stripe de produção nem medem carga real. **Gate da Fase 1 de código: aprovado.**
A documentação foi registrada posteriormente; o CI desse commit de documentação
deve ser consultado independentemente.

**Manual de operação e riscos:** `docs/SAAS_FASE_1_B2C_PREMIUM.md`.
Pendências de homologação externa: Stripe B2B end-to-end, teste de cargas
PDF e concorrência de quota em alta demanda, monitoramento/observabilidade,
backup/restore, MFA, staging, legislação tributária e cobrança real.
Nenhum dado de cartão nem chave secreta foi adicionado ao repositório.

## Fase 2 (prompt mestre v2) — Homologação Billing B2C/B2B Stripe Sandbox (09/10/2026)

**Escopo de código implementado diretamente na Saas-ChurrasPlan:** a tabela
comercial mensal aprovada é Premium R$ 9,90, Mercado Pro (Básico) R$ 49,90
e Mercado Business (Pro) R$ 99,90; novos campos STRIPE_EXPECTED_*_MONTHLY_CENTS
validam o unit_amount real de Stripe Test, rejeitam Price ID duplicado ou de
modo live e impedem Checkout divergente (HTTP 503). Periodicidade anual
fica indisponível até aprovar STRIPE_EXPECTED_*_YEARLY_CENTS>0; o catálogo
mensal permanece utilizável mesmo se houver Price ID anual ainda não homologado.

**Autenticação e retorno Stripe Checkout:** Premium pessoal retorna à
minha-conta.html?assinatura=retorno; mercados retornam à
minha-conta.html?cobranca=retorno&organizacao_id=ID. O login preserva os
parâmetros da URL; o backend B2B reconcilia Checkout local pago via Stripe Test
somente após verificar sessão complete, payment_status paid, metadata de
titularidade/plano/período, assinatura remota e proprietário da organização.
O Customer Portal B2C/B2B também retorna a Minha conta.

**Ciclo de vida:** em ambas as verticais, renovação e inadimplência por
webhook seguem o snapshot Stripe; B2C exige status active e período vigente,
B2B conserva a tolerância limitada original. Novas APIs B2C para faturas,
cancelamento agendado, reativação e troca de mensal/anual aprovada; B2B
mantém troca/cancelamento/faturas e ganha reativação e recuperação segura de
Checkout com webhook atrasado. Frontend de Minha Conta/painel do parceiro
permite consultar/gerir dados financeiros de Sandbox.
Sem novas migrations; preservados banco, planejamentos e entitlements.

**Cobertura e evidências:** tests/test_billing_fase2.py verifica erro de preço,
colisão de IDs, bloqueio de live, aprovação anual, faturas, Checkout retornado
sem pagamento e com pagamento confirmado, senha/sessão, RBAC multi-org, renovação,
past_due, unpaid, cancelamento, reativação, troca de período, webhook e
titularidade. Seguem suites test_billing_saas.py e
test_billing_usuario_stripe.py. CI #38003892454, do commit de código
1df5f0570d059e6904c65e5e03e051842f049fd7: pytest SQLite
**167 passed**, MySQL real/Alembic **12 passed**, frontend static, segurança
e Docker aprovados na consulta; E2E Chromium ainda precisava concluir
naquele instante. CodeQL #38003892428 em execução na mesma verificação.
Consultar estado final no GitHub antes de dar o gate como aprovado.

**Runbook:** docs/SAAS_FASE_2_HOMOLOGACAO_BILLING.md. Como a conexão Stripe
disponível nesta execução mostrou apenas conta em live mode, nenhum produto,
Price ID, pagamento, customer ou assinatura real foi alterado; a homologação
externa do Dashboard Sandbox (cartão de teste, webhooks, renovação com Test
Clocks se aplicável, valores anuais aprovados) permanece pendente de execução
no ambiente do mantenedor. Isso impede chamar a homologação externa de
concluída, apesar dos testes automatizados.

**Próximo passo do prompt mestre v2: Fase 3 — experiência empresarial B2B.**
Revalidar onboarding de parceiro, multi-organizações e filiais, permissões
da equipe, preços/referências, produtos genéricos, CSV de catálogo, ofertas,
campanhas moderadas, limites por plano, indicadores de interação, integração
gradual com mercados e testes de isolamento sem oferecer transações de venda
não verificadas como métricas de receita.
