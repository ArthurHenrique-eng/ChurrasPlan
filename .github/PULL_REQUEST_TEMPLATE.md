## Fase e objetivo
<!-- Ex.: Fase 1 / correção de cadastro de estabelecimentos -->

## Mudanças e compatibilidade
<!-- Arquivos, APIs, UX B2C/B2B/admin, efeitos nos cálculos determinísticos, dados legados. -->

## Banco / migrations
<!-- Nenhuma; ou objetivo, índices, constraints, migração de dados, rollback e testes MySQL. -->

## Evidência de teste
<!-- Comando | Ambiente | Resultado | Link para execução GitHub Actions. Não declarar verde sem verificar. -->

- [ ] Backend unit/integration (SQLite)
- [ ] MySQL 8 real + Alembic
- [ ] Frontend static checks
- [ ] Security audit
- [ ] Docker configuration and images
- [ ] E2E Chromium + MySQL
- [ ] Regressões do domínio e autorização revisadas

## Riscos, bloqueios e operações humanas
<!-- Credenciais/sandbox, domínio, restore real, parecer jurídico e demais limites. -->

## Gate de aceite
- [ ] Fase anterior revisada/integrada
- [ ] Critérios de aceitação demonstrados
- [ ] Sem merge automático nem declarações de operação real sem evidência
