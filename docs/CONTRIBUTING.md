# Contribuir

Leia README.md, AGENTS.md e docs/ChurrasPlanSaaS.md. Abra mudanças na branch SaaS indicada pelo mantenedor; main recebe apenas releases aprovadas.

Use commits por domínio (`fix(auth): ...`, `feat(growth): ...`). Toda mudança persistente usa Alembic, nunca create_all em produção. O schema.sql serve somente como referência de instalação nova.

Antes do PR, execute `scripts/test_all.sh` (Windows: scripts/test_all.ps1), confira MySQL/Alembic, testes do navegador e auditoria de dependências. Descreva problema, comportamento final, testes e gates externos. Consulte SECURITY.md para comunicar vulnerabilidades.

Versionamento: SemVer para a API; migrations são append-only depois de publicadas. Não reescreva migrations instaladas, publique a correção em nova revisão.
