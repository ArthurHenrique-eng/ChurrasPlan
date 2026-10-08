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
- **Pendente nas Fases 1/3/7:** MFA, observabilidade operacional, backups/restore externo, gateway de cobrança real com sandbox/webhooks, infraestrutura de staging e homologação para piloto. Não declarar disponibilidade comercial antes dessas validações.

## Fase 4A — Catálogo e campanhas

Incremento realizado diretamente em `Saas-ChurrasPlan`: importação CSV de SKU por organização com upsert e idempotência, campanhas de ofertas próprias com submissão, moderação administrativa, data de início/fim e cancelamento, listagem pública exclusivamente de campanhas elegíveis. Runbook e contratos: `docs/SAAS_FASE_4A_CATALOGO_CAMPANHAS.md`. Ainda faltam campanhas de mídia paga, integração ERP, prova de vendas transacionais, integração de compras reais e billing da Fase 3.
