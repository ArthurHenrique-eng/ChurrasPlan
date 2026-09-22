"""Alinha índices, FKs e nullability das fases 3-6.

Esta revisão fecha diferenças que não afetam os dados, mas são importantes para
que o schema criado por migrations seja equivalente ao metadata do ORM em
MySQL e também no SQLite usado pela suíte de validação.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0003"
down_revision = "20260918_0002"
branch_labels = None
depends_on = None


def _indexes(bind, table):
    return {i.get("name") for i in sa.inspect(bind).get_indexes(table)}


def _idx(bind, name, table, columns, unique=False):
    if name not in _indexes(bind, table):
        op.create_index(name, table, columns, unique=unique)


def _has_fk(bind, table, column, target_table, target_col="id", ondelete=None):
    for fk in sa.inspect(bind).get_foreign_keys(table):
        if fk.get("constrained_columns") != [column]:
            continue
        referred_cols = fk.get("referred_columns") or []
        current_delete = ((fk.get("options") or {}).get("ondelete") or "").upper()
        if fk.get("referred_table") == target_table and referred_cols == [target_col]:
            if (ondelete or "").upper() == current_delete:
                return True
    return False


def _ensure_fk(bind, table, column, target_table, *, ondelete=None, name=None):
    if _has_fk(bind, table, column, target_table, ondelete=ondelete):
        return
    # batch_alter_table recria a tabela quando necessário no SQLite e usa
    # ALTER TABLE normal em bancos que o suportam.
    with op.batch_alter_table(table) as batch:
        batch.create_foreign_key(
            name or f"fk_{table}_{column}", target_table,
            [column], ["id"], ondelete=ondelete,
        )


def upgrade():
    bind = op.get_bind()

    for name, table, cols in [
        ("ix_churrascos_usuario_id", "churrascos", ["usuario_id"]),
        ("ix_churrascos_status", "churrascos", ["status"]),
        ("ix_churrascos_data_evento", "churrascos", ["data_evento"]),
        ("ix_usuarios_papel", "usuarios", ["papel"]),
        ("ix_produtos_sku", "produtos", ["sku"]),
        ("ix_estabelecimentos_latitude", "estabelecimentos", ["latitude"]),
        ("ix_estabelecimentos_longitude", "estabelecimentos", ["longitude"]),
    ]:
        _idx(bind, name, table, cols)

    _ensure_fk(bind, "produtos", "produto_pai_id", "produtos", ondelete="SET NULL", name="fk_produtos_produto_pai")
    _ensure_fk(bind, "estabelecimentos", "usuario_responsavel_id", "usuarios", ondelete="SET NULL", name="fk_estabelecimentos_usuario_responsavel")
    _ensure_fk(bind, "precos", "criado_por_usuario_id", "usuarios", ondelete="SET NULL", name="fk_precos_criado_por_usuario")
    _ensure_fk(bind, "lista_compras_itens", "estabelecimento_compra_id", "estabelecimentos", ondelete="SET NULL", name="fk_lista_item_estabelecimento_compra")

    # As duas colunas são preenchidas antes de torná-las NOT NULL.
    op.execute("UPDATE usuarios SET criado_em=COALESCE(criado_em, CURRENT_TIMESTAMP)")
    op.execute("UPDATE usuarios SET atualizado_em=COALESCE(atualizado_em, criado_em, CURRENT_TIMESTAMP)")
    with op.batch_alter_table("usuarios") as batch:
        batch.alter_column("criado_em", existing_type=sa.DateTime(), nullable=False)
        batch.alter_column("atualizado_em", existing_type=sa.DateTime(), nullable=False)


def downgrade():
    # Downgrade conservador: índices de performance podem ser removidos sem
    # perda de dados; FKs e NOT NULL ficam preservados para não enfraquecer a
    # integridade de um banco que já recebeu dados das fases 3-6.
    bind = op.get_bind()
    for name, table in [
        ("ix_estabelecimentos_longitude", "estabelecimentos"),
        ("ix_estabelecimentos_latitude", "estabelecimentos"),
        ("ix_produtos_sku", "produtos"),
        ("ix_usuarios_papel", "usuarios"),
        ("ix_churrascos_data_evento", "churrascos"),
        ("ix_churrascos_status", "churrascos"),
        ("ix_churrascos_usuario_id", "churrascos"),
    ]:
        if name in _indexes(bind, table):
            op.drop_index(name, table_name=table)
