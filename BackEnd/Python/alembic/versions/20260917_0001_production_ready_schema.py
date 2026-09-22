"""Baseline/evolução para o modelo consistente v0.2.

A revisão é tolerante ao banco legado do MVP. Bancos vazios são criados já no
modelo atual. Bancos existentes recebem os campos, tipos e constraints novos
sem reinterpretar silenciosamente ofertas antigas cuja unidade comercial não
pode ser garantida.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260917_0001"
down_revision = None
branch_labels = None
depends_on = None


# Produtos existentes no seed do MVP original. O mapeamento é deliberadamente
# congelado na migration para que ela não dependa do config.py de versões futuras.
LEGACY_PRODUCTS = {
    "Picanha": ("picanha", "kg", "kg", True, 0.10, None, None),
    "Alcatra": ("alcatra", "kg", "kg", True, 0.10, None, None),
    "Linguiça": ("linguica", "kg", "kg", True, 0.10, None, None),
    "Frango": ("frango", "kg", "kg", True, 0.10, None, None),
    "Carvão": ("carvao", "kg", "saco", False, None, 3.0, "kg"),
    "Água": ("agua", "litro", "garrafa", False, None, 1.5, "litro"),
    "Refrigerante": ("refrigerante", "litro", "garrafa", False, None, 2.0, "litro"),
    "Cerveja": ("cerveja", "litro", "lata", False, None, 0.35, "litro"),
    "Gelo": ("gelo", "kg", "saco", False, None, 5.0, "kg"),
}

LEGACY_ESTABLISHMENTS = {
    "Supermercado Exemplo Centro": "supermercado-exemplo-centro",
    "Açougue Exemplo Bairro": "acougue-exemplo-bairro",
}


def _columns(inspector, table):
    return {c["name"] for c in inspector.get_columns(table)}


def _add_if_missing(inspector, table, column):
    if column.name not in _columns(inspector, table):
        op.add_column(table, column)
        return True
    return False


def _index_names(bind, table):
    return {i["name"] for i in sa.inspect(bind).get_indexes(table) if i.get("name")}


def _has_unique(bind, table, columns):
    inspector = sa.inspect(bind)
    wanted = list(columns)
    if any(i.get("unique") and i.get("column_names") == wanted for i in inspector.get_indexes(table)):
        return True
    return any(u.get("column_names") == wanted for u in inspector.get_unique_constraints(table))


def _replace_fk_mysql(bind, table, local_column, referred_table, referred_column="id", ondelete=None, name=None):
    """Normaliza ON DELETE em MySQL; banco novo já nasce correto pelo metadata."""
    if bind.dialect.name != "mysql":
        return
    inspector = sa.inspect(bind)
    target = None
    for fk in inspector.get_foreign_keys(table):
        if fk.get("constrained_columns") == [local_column]:
            target = fk
            break
    desired = (ondelete or "").upper()
    current = ((target or {}).get("options") or {}).get("ondelete", "").upper()
    if target and current == desired:
        return
    if target and target.get("name"):
        op.drop_constraint(target["name"], table, type_="foreignkey")
    op.create_foreign_key(
        name or f"fk_{table}_{local_column}", table, referred_table,
        [local_column], [referred_column], ondelete=ondelete,
    )


def _map_legacy_products(bind):
    rows = bind.execute(sa.text("SELECT id, nome, slug FROM produtos")).mappings().all()
    by_slug = {r["slug"]: r["id"] for r in rows if r["slug"]}
    for row in rows:
        spec = LEGACY_PRODUCTS.get(row["nome"])
        if not spec:
            continue
        slug, unidade_consumo, unidade_venda, fracionada, incremento, embalagem, unidade_embalagem = spec
        target_id = by_slug.get(slug)
        if target_id and target_id != row["id"]:
            # Se um catálogo v2 já foi parcialmente inserido, preserva o ID v2 e
            # reconecta histórico/referências do produto legado antes de inativá-lo.
            for table in ["precos", "churrasco_carnes", "churrasco_bebidas", "churrasco_extras", "lista_compras_itens"]:
                if table in sa.inspect(bind).get_table_names() and "produto_id" in _columns(sa.inspect(bind), table):
                    bind.execute(sa.text(f"UPDATE {table} SET produto_id=:target WHERE produto_id=:old"), {"target": target_id, "old": row["id"]})
            bind.execute(sa.text("UPDATE produtos SET ativo=FALSE WHERE id=:id"), {"id": row["id"]})
            continue
        bind.execute(sa.text("""
            UPDATE produtos
               SET slug=:slug, unidade_consumo=:uc, unidade_venda=:uv,
                   venda_fracionada=:vf, incremento_venda=:inc,
                   quantidade_embalagem=:qe, unidade_embalagem=:ue, ativo=TRUE
             WHERE id=:id
        """), {
            "slug": slug, "uc": unidade_consumo, "uv": unidade_venda,
            "vf": fracionada, "inc": incremento, "qe": embalagem,
            "ue": unidade_embalagem, "id": row["id"],
        })
        by_slug[slug] = row["id"]


def _map_legacy_establishments(bind):
    rows = bind.execute(sa.text("SELECT id, nome, slug FROM estabelecimentos")).mappings().all()
    used = {r["slug"] for r in rows if r["slug"]}
    for row in rows:
        desired = LEGACY_ESTABLISHMENTS.get(row["nome"])
        if desired and desired not in used:
            bind.execute(sa.text("UPDATE estabelecimentos SET slug=:slug WHERE id=:id"), {"slug": desired, "id": row["id"]})
            used.add(desired)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    # O Alembic cria `alembic_version` antes de chamar upgrade(); ela não
    # significa que exista um schema de aplicação a migrar.
    application_tables = tables - {"alembic_version"}
    if not application_tables:
        # Snapshot congelado: uma migration antiga nunca deve importar o
        # metadata atual da aplicação, pois isso mudaria seu comportamento
        # quando novos models fossem adicionados no futuro.
        from migration_snapshots.v02 import BaseV02
        BaseV02.metadata.create_all(bind=bind)
        return

    # Churrascos: inclui os campos que historicamente faltavam no schema.sql.
    for col in [
        sa.Column("perfil_personalizado", sa.JSON(), nullable=True),
        sa.Column("carvao_ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("gelo_ativo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("chave_cliente", sa.String(64), nullable=True),
        sa.Column("carvao_necessario_kg", sa.Numeric(12, 3), nullable=True),
        sa.Column("carvao_compra_kg", sa.Numeric(12, 3), nullable=True),
    ]:
        _add_if_missing(inspector, "churrascos", col)
        inspector = sa.inspect(bind)

    # O MVP antigo guardava em `carvao_kg` a quantidade de compra. Esse valor
    # pode ser preservado como compra, mas a necessidade exata não é inferida
    # artificialmente para históricos antigos.
    churrasco_cols = _columns(inspector, "churrascos")
    if "carvao_kg" in churrasco_cols:
        bind.execute(sa.text("UPDATE churrascos SET carvao_compra_kg=COALESCE(carvao_compra_kg,carvao_kg)"))

    # Identidade estável e representação da embalagem comercial.
    product_cols = [
        sa.Column("slug", sa.String(140), nullable=True),
        sa.Column("unidade_consumo", sa.String(30), nullable=True),
        sa.Column("venda_fracionada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("incremento_venda", sa.Numeric(12, 3), nullable=True),
        sa.Column("quantidade_embalagem", sa.Numeric(12, 3), nullable=True),
        sa.Column("unidade_embalagem", sa.String(30), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]
    for col in product_cols:
        _add_if_missing(inspector, "produtos", col)
        inspector = sa.inspect(bind)
    bind.execute(sa.text("UPDATE produtos SET slug = CONCAT('legacy-', id) WHERE slug IS NULL" if bind.dialect.name == "mysql" else "UPDATE produtos SET slug = 'legacy-' || id WHERE slug IS NULL"))
    bind.execute(sa.text("UPDATE produtos SET unidade_consumo = unidade_venda WHERE unidade_consumo IS NULL"))
    _map_legacy_products(bind)

    for col in [
        sa.Column("slug", sa.String(170), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]:
        _add_if_missing(inspector, "estabelecimentos", col)
        inspector = sa.inspect(bind)
    bind.execute(sa.text("UPDATE estabelecimentos SET slug = CONCAT('legacy-', id) WHERE slug IS NULL" if bind.dialect.name == "mysql" else "UPDATE estabelecimentos SET slug = 'legacy-' || id WHERE slug IS NULL"))
    _map_legacy_establishments(bind)

    # Ofertas antigas são mantidas no histórico, mas ficam indisponíveis se o
    # campo `disponivel` precisou ser criado: o MVP não registrava a embalagem
    # à qual aquele preço se referia, então reutilizá-lo seria matematicamente inseguro.
    added_disponivel = False
    for col in [
        sa.Column("fonte", sa.String(255), nullable=True),
        sa.Column("disponivel", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("coletado_em", sa.DateTime(), nullable=True),
    ]:
        added = _add_if_missing(inspector, "precos", col)
        if col.name == "disponivel":
            added_disponivel = added
        inspector = sa.inspect(bind)
    bind.execute(sa.text("UPDATE precos SET coletado_em = COALESCE(data_atualizacao, CURRENT_TIMESTAMP) WHERE coletado_em IS NULL"))
    if added_disponivel:
        bind.execute(sa.text("UPDATE precos SET disponivel=FALSE, fonte=COALESCE(fonte, 'legacy-unidade-nao-confirmada')"))

    # Campos calculados/snapshot em carnes, bebidas e extras.
    comuns = [
        ("preco_id", sa.Integer()), ("produto_slug", sa.String(140)),
        ("quantidade_necessaria", sa.Numeric(12, 3)), ("unidade_necessaria", sa.String(30)),
        ("quantidade_compra", sa.Numeric(12, 3)), ("unidade_compra", sa.String(30)),
        ("quantidade_embalagens", sa.Integer()), ("tamanho_embalagem", sa.Numeric(12, 3)),
        ("unidade_embalagem", sa.String(30)), ("unidade_venda", sa.String(30)),
        ("preco_unitario", sa.Numeric(12, 2)), ("subtotal_estimado", sa.Numeric(12, 2)),
        ("estabelecimento_id", sa.Integer()),
    ]
    for table in ["churrasco_carnes", "churrasco_bebidas", "churrasco_extras"]:
        for name, typ in comuns:
            _add_if_missing(inspector, table, sa.Column(name, typ, nullable=True))
            inspector = sa.inspect(bind)

    cc = _columns(inspector, "churrasco_carnes")
    if "quantidade_kg" in cc:
        bind.execute(sa.text("""
            UPDATE churrasco_carnes
               SET quantidade_necessaria=COALESCE(quantidade_necessaria,quantidade_kg),
                   unidade_necessaria=COALESCE(unidade_necessaria,'kg'),
                   quantidade_compra=COALESCE(quantidade_compra,quantidade_kg),
                   unidade_compra=COALESCE(unidade_compra,'kg'),
                   unidade_venda=COALESCE(unidade_venda,'kg')
        """))
        with op.batch_alter_table("churrasco_carnes") as batch:
            batch.alter_column("quantidade_kg", existing_type=sa.Float(), nullable=True)
            batch.alter_column("percentual", existing_type=sa.Float(), type_=sa.Numeric(6, 2), nullable=False)

    for table in ["churrasco_bebidas", "churrasco_extras"]:
        cols = _columns(sa.inspect(bind), table)
        if "quantidade" in cols and "unidade" in cols:
            bind.execute(sa.text(f"""
                UPDATE {table}
                   SET quantidade_necessaria=COALESCE(quantidade_necessaria,quantidade),
                       unidade_necessaria=COALESCE(unidade_necessaria,unidade),
                       quantidade_compra=COALESCE(quantidade_compra,quantidade),
                       unidade_compra=COALESCE(unidade_compra,unidade),
                       unidade_venda=COALESCE(unidade_venda,unidade)
            """))
            with op.batch_alter_table(table) as batch:
                batch.alter_column("quantidade", existing_type=sa.Float(), nullable=True)
                batch.alter_column("unidade", existing_type=sa.String(20), nullable=True)

    # As colunas novas possuem valor para todas as linhas legadas após o backfill.
    for table in ["churrasco_carnes", "churrasco_bebidas", "churrasco_extras"]:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("quantidade_necessaria", existing_type=sa.Numeric(12, 3), nullable=False)
            batch.alter_column("unidade_necessaria", existing_type=sa.String(30), nullable=False)
            batch.alter_column("quantidade_compra", existing_type=sa.Numeric(12, 3), nullable=False)
            batch.alter_column("unidade_compra", existing_type=sa.String(30), nullable=False)
            batch.alter_column("unidade_venda", existing_type=sa.String(30), nullable=False)

    # Lista representa compra efetiva, não necessidade.
    for col in [
        sa.Column("produto_id", sa.Integer(), nullable=True),
        sa.Column("quantidade_embalagens", sa.Integer(), nullable=True),
        sa.Column("unidade_venda", sa.String(30), nullable=True),
        sa.Column("preco_unitario", sa.Numeric(12, 2), nullable=True),
        sa.Column("subtotal_estimado", sa.Numeric(12, 2), nullable=True),
    ]:
        _add_if_missing(inspector, "lista_compras_itens", col)
        inspector = sa.inspect(bind)
    bind.execute(sa.text("UPDATE lista_compras_itens SET unidade_venda=COALESCE(unidade_venda,unidade)"))

    # Tipos monetários/quantitativos consistentes também em bancos migrados.
    with op.batch_alter_table("produtos") as batch:
        batch.alter_column("slug", existing_type=sa.String(140), nullable=False)
        batch.alter_column("unidade_consumo", existing_type=sa.String(30), nullable=False)
    with op.batch_alter_table("estabelecimentos") as batch:
        batch.alter_column("slug", existing_type=sa.String(170), nullable=False)
    with op.batch_alter_table("precos") as batch:
        batch.alter_column("preco", existing_type=sa.Float(), type_=sa.Numeric(12, 2), nullable=False)
        batch.alter_column("coletado_em", existing_type=sa.DateTime(), nullable=False)
    with op.batch_alter_table("churrascos") as batch:
        for name in ["carne_total_kg"]:
            batch.alter_column(name, existing_type=sa.Float(), type_=sa.Numeric(12, 3), nullable=True)
        if "carvao_kg" in _columns(sa.inspect(bind), "churrascos"):
            batch.alter_column("carvao_kg", existing_type=sa.Float(), type_=sa.Numeric(12, 3), nullable=True)
        for name in ["custo_total_estimado", "custo_por_pessoa"]:
            batch.alter_column(name, existing_type=sa.Float(), type_=sa.Numeric(12, 2), nullable=True)
    with op.batch_alter_table("lista_compras_itens") as batch:
        batch.alter_column("quantidade", existing_type=sa.Float(), type_=sa.Numeric(12, 3), nullable=False)
        batch.alter_column("unidade", existing_type=sa.String(20), type_=sa.String(30), nullable=False)
        batch.alter_column("unidade_venda", existing_type=sa.String(30), nullable=False)

    # Constraints de exclusão alinhadas ao ORM/schema de referência.
    _replace_fk_mysql(bind, "precos", "produto_id", "produtos", ondelete="CASCADE", name="fk_precos_produto")
    _replace_fk_mysql(bind, "precos", "estabelecimento_id", "estabelecimentos", ondelete="CASCADE", name="fk_precos_estabelecimento")
    _replace_fk_mysql(bind, "churrascos", "usuario_id", "usuarios", ondelete="SET NULL", name="fk_churrascos_usuario")
    for table in ["churrasco_carnes", "churrasco_bebidas", "churrasco_extras"]:
        prefix = {"churrasco_carnes": "cc", "churrasco_bebidas": "cb", "churrasco_extras": "ce"}[table]
        _replace_fk_mysql(bind, table, "produto_id", "produtos", ondelete="SET NULL", name=f"fk_{prefix}_produto")
        _replace_fk_mysql(bind, table, "preco_id", "precos", ondelete="SET NULL", name=f"fk_{prefix}_preco")
        _replace_fk_mysql(bind, table, "estabelecimento_id", "estabelecimentos", ondelete="SET NULL", name=f"fk_{prefix}_estabelecimento")
    _replace_fk_mysql(bind, "lista_compras_itens", "produto_id", "produtos", ondelete="SET NULL", name="fk_lista_item_produto")

    # Índices únicos somente se ainda não existirem.
    if "uq_produtos_slug" not in _index_names(bind, "produtos") and not _has_unique(bind, "produtos", ["slug"]):
        op.create_index("uq_produtos_slug", "produtos", ["slug"], unique=True)
    if "uq_estabelecimentos_slug" not in _index_names(bind, "estabelecimentos") and not _has_unique(bind, "estabelecimentos", ["slug"]):
        op.create_index("uq_estabelecimentos_slug", "estabelecimentos", ["slug"], unique=True)
    if "uq_churrascos_chave_cliente" not in _index_names(bind, "churrascos") and not _has_unique(bind, "churrascos", ["chave_cliente"]):
        op.create_index("uq_churrascos_chave_cliente", "churrascos", ["chave_cliente"], unique=True)

    # Em MySQL, remove ON UPDATE herdado do preço legado: uma observação histórica
    # deve ser imutável; uma nova coleta gera uma nova linha.
    if bind.dialect.name == "mysql":
        op.execute("ALTER TABLE precos MODIFY data_atualizacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")


def downgrade():
    # Downgrade destrutivo não é automatizado para preservar dados do legado.
    pass
