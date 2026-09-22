# Validação da revisão v0.2

Validações executadas no pacote antes da entrega:

- `pytest -q` com SQLite em memória: **67 passed**.
- `python -m compileall`: sem erro de compilação Python.
- `node --check` em todos os arquivos `FrontEnd/js/*.js`: sem erro de sintaxe.
- Alembic em banco vazio SQLite: migration `20260917_0001` aplicada e schema criado.
- Alembic sobre réplica SQLite do schema legado: dados preservados, produtos legados conhecidos normalizados, preços antigos preservados como histórico indisponível e novos campos criados.
- Paridade de colunas ORM → `sql/schema.sql`: nenhuma coluna de model ausente no SQL de referência.
- Paridade do catálogo de carnes: 23 slugs no frontend e 23 no catálogo central do backend, sem diferença.
- Varredura por padrões obsoletos auditados (`18,3`, pacote global de 2 kg, `query().get`, `class Config` Pydantic v1 e dinheiro modelado como Float): nenhum uso funcional remanescente.

## Limitação do ambiente de validação

O ambiente da revisão não possui daemon/cliente MySQL instalado. Por isso, a migration foi executada de verdade nos cenários vazio e legado usando SQLite, enquanto os trechos específicos de MySQL (normalização de `ON DELETE` e remoção de `ON UPDATE` do preço legado) foram validados por inspeção/código, não contra uma instância MySQL ativa. O alvo de produção continua sendo MySQL 8+ e o passo recomendado antes de publicar é aplicar `alembic upgrade head` em um clone/backup do banco MySQL real e executar um smoke test da API.
