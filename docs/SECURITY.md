# Segurança

A branch Saas-ChurrasPlan está em preparação para lançamento. Reporte falhas pelo recurso privado de relato de vulnerabilidade do GitHub, quando habilitado; não inclua tokens, senhas, dados reais ou provas que acessem contas de terceiros em issues públicas.

Superfícies críticas: sessões/cookies/CSRF, MFA, convites públicos, isolamento por organização, permissões, importações, preços, entitlements e webhooks. Dados de uma organização devem permanecer inacessíveis a membros de outra. Nenhum input do navegador pode ativar assinatura paga ou aprovar estabelecimento/campanha.

Preços estimativos e métricas de intenção não são transações. Integrações externas usam destinos controlados, timeout e limites. Senhas usam Argon2id, segredos MFA/outbox usam cifra autenticada e backups usam chave independente.

Antes de release: resolver vulnerabilidades críticas/altas, executar CI/CodeQL e pip-audit, confirmar MFA administrativo, TLS, SMTP, isolamento, backup/restore e rollback em staging. Configurações externas e permissões GitHub devem ser conferidas na conta real.
