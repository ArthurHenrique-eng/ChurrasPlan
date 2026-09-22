"""Métricas agregadas de estabelecimentos para o painel de parceiros.

A tabela registra somente estabelecimento, tipo de interação, contexto e data.
Não persiste usuário, churrasco, sessão, IP ou coordenadas de quem visualizou/clicou.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0004"
down_revision = "20260918_0003"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "metricas_estabelecimentos" not in tables:
        op.create_table(
            "metricas_estabelecimentos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("estabelecimento_id", sa.Integer(), nullable=False),
            sa.Column("tipo", sa.String(20), nullable=False),
            sa.Column("contexto", sa.String(40), nullable=False, server_default="onde_comprar"),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ["estabelecimento_id"], ["estabelecimentos.id"],
                ondelete="CASCADE", name="fk_metricas_estabelecimentos_estabelecimento",
            ),
            sa.CheckConstraint(
                "tipo IN ('visualizacao','clique')",
                name="ck_metricas_estabelecimentos_tipo",
            ),
        )

    inspector = sa.inspect(bind)
    indices = {i.get("name") for i in inspector.get_indexes("metricas_estabelecimentos")}
    for nome, colunas in [
        ("ix_metricas_estabelecimentos_id", ["id"]),
        ("ix_metricas_estabelecimentos_estabelecimento_id", ["estabelecimento_id"]),
        ("ix_metricas_estabelecimentos_tipo", ["tipo"]),
        ("ix_metricas_estabelecimentos_criado_em", ["criado_em"]),
        ("ix_metricas_estabelecimentos_estabelecimento_tipo_criado", ["estabelecimento_id", "tipo", "criado_em"]),
    ]:
        if nome not in indices:
            op.create_index(nome, "metricas_estabelecimentos", colunas, unique=False)
            indices.add(nome)


def downgrade():
    bind = op.get_bind()
    if "metricas_estabelecimentos" in set(sa.inspect(bind).get_table_names()):
        op.drop_table("metricas_estabelecimentos")
