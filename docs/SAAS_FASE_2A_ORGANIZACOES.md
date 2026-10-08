# Fase 2A — Organizações, membros e isolamento de operações B2B

## Gate de entrada e escopo
A branch `Saas-ChurrasPlan` integrou os PRs #3–#6; CI de push no merge commit `a98d0f72c93610a0924a406fc21894720631de56`: [run 37819345671](https://github.com/ArthurHenrique-eng/ChurrasPlan/actions/runs/37819345671), **6/6 verde**; CodeQL em push com ambas linguagens verdes.

A primeira fatia do núcleo multi-tenant estabelece **organizações, membros, papel local, vínculo de mercados e propriedade de SKU comercial**. Não implementa cobrança, alteração de plano, onboarding por convite, entitlements/quota ou múltiplas filiais gerenciadas em interface.

## Modelagem e migrations
- Migration `20261008_0009` cria `organizacoes` e `organizacao_membros`, com `UNIQUE(organizacao_id, usuario_id)`, FK/cascade e papéis locais `proprietario`, `gestor`, `editor`, `leitor`.
- Adiciona `organizacao_id` **nullable** a `estabelecimentos` e `produtos`, sem remover `usuario_responsavel_id` nem alterar IDs, preços, históricos, convidados, cálculos e listas.
- Backfill de parceiros existentes e proprietários de estabelecimentos para organizações isoladas; vínculo original de usuário permanece. Estabelecimentos externos sem responsável não recebem organização arbitrária.
- SKU comercial legado com oferta em apenas uma organização recebe essa organização. SKUs sem oferta ou partilhados por mais de uma organização **ficam com `organizacao_id=NULL`** até conciliação manual, sem criar atribuição falsa.
- Downgrade remove apenas a estrutura nova, preservando `usuario_responsavel_id`, SKUs, preços e demais dados legados. Após novo upgrade, as associações determinísticas são refeitas; IDs de organização poderão mudar, portanto não persistir relações externas baseadas em seus IDs antes de estabilizar a migration.

## Isolamento e contratos API
- `POST /api/parceiro/ativar`: cria a primeira organização e vínculo `proprietario` no mesmo commit de ativação, de maneira idempotente. A promoção pelo administrador também provisiona uma organização para evitar bloqueio do painel. Lock do usuário e leitura corrente dos membros serializam duas ativações simultâneas no MySQL. Administradores preservam fluxos globais existentes.
- `GET /api/parceiro/organizacoes`: lista apenas organizações ativas das quais o usuário é membro ativo; **não permite listar organizações alheias por ID**.
- `X-Organizacao-ID`: opcional para quem tem uma única organização, **obrigatório se for membro de várias** (HTTP 409 sem seleção); organização alheia ou desativada retorna HTTP 404.
- Rotas `/api/parceiro/estabelecimentos` GET/POST/PUT, `/dashboard`, `/produtos` GET/POST e `/precos` POST consultam contexto e associações no backend, não confiam no ID fornecido pelo frontend.
- `leitor` consulta mas não muta (HTTP 403). `gestor`, `editor`, `proprietario` podem editar; operações do `admin` global mantêm compatibilidade.
- SKUs criados por parceiros recebem organização; a listagem **privada** comercial é filtrada por organização e impede cadastrar uma oferta de SKU pertencente a outro tenant. Genéricos e SKUs legados explicitamente sem dono continuam catálogo compartilhado para fins de preços. O catálogo público B2C continua global para preservar busca e planejamento.

## Testes / gate obrigatório
- SQLite: ativações idempotentes, organização de origem, acesso cross-tenant negado mesmo com cabeçalho forjado, manipulação de mercados/preços bloqueada, listagens isoladas, papel `leitor` e múltiplas organizações.
- MySQL 8.4 real: aplicar Alembic até `20260925_0008`, registrar uma conta + mercado + SKU + oferta legados **somente no CI**, fazer upgrade ao novo head e confirmar que dados, valores e proprietários permanecem; `alembic check`.
- Ainda no banco **efêmero de CI**, executar `alembic downgrade -1` → `upgrade head` → `alembic check` e testar novamente o backfill.
- Frontend sintaxe/PWA, segurança, Docker e E2E completos continuam obrigatórios.

## Limites — não declarar conclusão integral da Fase 2
- **Entitlements e quotas** centralizados, planos Free/Pro/Business, cobrança, renovação e suspensão precisam dos PRs seguintes.
- Convites para novos membros, mudança de papéis, transferência de propriedade, exclusão/desativação de org e seletor visual multi-org ainda não são implementados. A API exige cabeçalho para contas com múltiplas organizações.
- SKUs legados sem vínculo inequívoco devem ser reconciliados por procedimento auditável antes de conceder permissões de administração; não atribuir automaticamente a uma organização.
- Rotas públicas de catálogo continuam expondo dados comerciais publicáveis; auditar informações privadas, relatórios e todas as operações B2B conforme expansão da Fase 2.
- O fluxo de MFA, monitoramento/backup externo, proteção de branch e deploy do roadmap seguem pendentes e bloqueiam classificação como SaaS comercial pronto.

## Rollback e operação
Nenhum deploy ou dado de produção foi tocado. Backup/restore real é pré-requisito de uma migração em produção; validar versão com `alembic current`. Nunca executar seed CI fora do MySQL descartável. Rollback em ambiente novo com migração revertida e testes; em produção, preferir rollback da aplicação compatível com colunas novas sem eliminá-las até validação humana.
