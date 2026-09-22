# Validação da release — ChurrasPlan v3.0

Data de consolidação: 18/09/2026.

## Suíte automatizada

Comando:

```bash
cd BackEnd/Python
DATABASE_URL=sqlite:///:memory: pytest -q
```

Resultado final desta release:

```text
83 passed
```

A suíte cobre o núcleo matemático anterior e regressões das fases 3–6, incluindo:

- autenticação/sessão;
- CSRF;
- orçamento completo e parcial;
- restrições alimentares;
- histórico e repetição;
- convite/RSVP;
- RSVP idempotente/editável;
- checklist/valor realmente pago;
- divisão com prioridade ao valor real quando completo;
- produtos comerciais/SKU;
- preços de parceiro;
- bloqueio público de oferta de parceiro não verificado;
- otimização;
- configuração insegura de produção;
- métricas de visualização/clique e ausência de identificador pessoal no modelo de métricas.

## Migrations

### Banco vazio

Executado:

```text
alembic upgrade head
```

Resultado:

```text
head = 20260918_0004
metricas_estabelecimentos criada
```

### Upgrade de banco v0.2 com dados

Um banco foi levado até `20260917_0001`, recebeu usuário e churrasco de teste e depois foi atualizado até o `head`.

Validação:

- usuário legado preservado;
- churrasco legado preservado;
- `adultos` preenchido a partir de `homens + mulheres`;
- `adultos_bebem_alcool` preenchido a partir dos campos legados;
- nova tabela de métricas criada;
- revisão final `20260918_0004`.

### Alembic autogenerate check

Executado no banco migrado:

```text
alembic check
```

Resultado:

```text
No new upgrade operations detected.
```

Isso comprova alinhamento entre o metadata atual do ORM e o schema resultante das migrations no mecanismo de validação usado.

## Schema SQL

`sql/schema.sql` foi regenerado a partir do metadata ORM atual usando dialeto MySQL e contém as 18 tabelas da aplicação, incluindo `metricas_estabelecimentos`.

A evolução oficial continua sendo via Alembic.

## Frontend

Validações de release previstas/executadas no fechamento:

- sintaxe de todos os arquivos JavaScript com `node --check`;
- referências locais de CSS/JS/imagens;
- IDs duplicados por documento;
- arquivos exigidos pelas páginas;
- parsing estrutural dos arquivos HTML/CSS.

## Observação sobre MySQL real

As migrations e o schema são direcionados a MySQL 8+, porém a automação desta sessão executou migrations de validação em SQLite. Antes de colocar em produção, aplique `alembic upgrade head` em uma cópia/staging do **mesmo MySQL** usado na hospedagem e execute um smoke test completo. Isso não deve ser substituído por confiança apenas na suíte SQLite.
