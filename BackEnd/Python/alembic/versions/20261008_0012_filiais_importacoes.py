"""Fase 2D: identificação de filiais e importação idempotente de ofertas.

Revision ID: 20261008_0012
Revises: 20261008_0011
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0012"
down_revision = "20261008_0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("estabelecimentos", sa.Column("codigo_filial", sa.String(40), nullable=True))
    op.add_column("estabelecimentos", sa.Column("unidade_matriz", sa.Boolean(), nullable=False, server_default="0"))
    op.create_unique_constraint("uq_estabelecimentos_org_codigo_filial", "estabelecimentos", ["organizacao_id", "codigo_filial"])
    op.create_table(
        "importacoes_ofertas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chave_idempotencia", sa.String(80), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("resultado", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organizacao_id", "chave_idempotencia", name="uq_importacao_ofertas_org_chave"),
    )
    op.create_index("ix_importacoes_ofertas_organizacao_id", "importacoes_ofertas", ["organizacao_id"])


def downgrade():
    # Descarta somente logs de importações; registros de preços já aplicados permanecem.
    op.drop_table("importacoes_ofertas")
    op.drop_constraint("uq_estabelecimentos_org_codigo_filial", "estabelecimentos", type_="unique")
    op.drop_column("estabelecimentos", "unidade_matriz")
    op.drop_column("estabelecimentos", "codigo_filial")
