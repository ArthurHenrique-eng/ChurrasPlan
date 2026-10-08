# Roadmap SaaS — PR por fase, gates de qualidade

Branch-base exclusiva para integração SaaS: `Saas-ChurrasPlan` (não `main`). Criar `saas/fase-N-...` **a partir do último commit da branch-base** e abrir PR com base `Saas-ChurrasPlan`. Não comitar diretamente na branch-base, pois isso inviabiliza a revisão de PR. Não fazer merge automático; exigir revisão, check de cada job e ausência de falhas introduzidas. Uma fase ampla pode precisar de **vários PRs pequenos dentro do mesmo marco**, mantendo foco por domínio técnico; jamais empilhar fases sem passar pelos gates.

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

## Regras para cada PR

1. Listar escopo, arquivos alterados, migrations e contrato de API; registrar efeitos B2C/B2B/admin.
2. Demonstrar comandos, testes passados/falhos, referências à execução GitHub Actions e limitações de ambiente.
3. Testar no MySQL real quando houver persistência; validar `alembic check`, retenção de dados legados e rollback adequado.
4. Cobrir segurança de rota por backend: CSRF, papéis, isolamento organizacional, rate limit, webhooks autenticados e idempotência conforme escopo.
5. Evidenciar impacto no planejador: regras determinísticas, preços (referência vs oferta), PWA, e fronteiras entre compra física e quantidade comercial.
6. Não esconder falhas de CI nem declarar integrações externas ativas sem sandbox/produção demonstrados.
7. Bloquear merge com falhas dos jobs: `Backend unit/integration (SQLite)`, `MySQL 8 real + Alembic`, `Frontend static checks`, `Security audit`, `Docker configuration and images`, `E2E Chromium + MySQL`.
8. Atualizar esse roadmap com o status **somente depois** da prova e revisão. Sem assinatura paga fictícia, sem deploy/push para `main`.

## Dependências arquiteturais

`B2C estável` → `organizações e isolamento` → `entitlements` → `billing sandbox integrado` → `operação B2B escalável` → `funis e valor demonstrável` → `piloto e validação comercial`.

Dependências humanas explícitas: configurar conta real de cobrança, chaves/contratos, DNS e servidores, backups externos, consultoria jurídica/tributária, recrutamento de parceiros e validação de disposição a pagar. Parte técnica pode ser desenvolvida com adapters/mocks/sandbox, sem simular resultado financeiro real.

## Próximo PR sugerido (após Fase 0 aprovada)

`saas/fase-1-correcao-cadastro-catalogo-precos`: priorizar exclusivamente os três fluxos P0 relatados; novos testes Playwright de parceiro/admin e regressão de orçamentos; ajustar `README.md`/Compose no mesmo marco, idealmente commit separado. MFA/CSP/observabilidade/backup entram em incrementos separados de Fase 1 para não concentrar riscos numa revisão única.
