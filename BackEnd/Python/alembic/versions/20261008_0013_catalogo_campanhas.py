"""Fase 4A: importações de catálogo e campanhas comerciais moderadas.

Revision ID: 20261008_0013
Revises: 20261008_0012
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0013"
down_revision = "20261008_0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "importacoes_catalogo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chave_idempotencia", sa.String(80), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("resultado", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organizacao_id", "chave_idempotencia", name="uq_importacoes_catalogo_org_chave"),
    )
    op.create_index("ix_importacoes_catalogo_organizacao_id", "importacoes_catalogo", ["organizacao_id"])
    op.create_table(
        "campanhas_comerciais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo", sa.String(60), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("descricao", sa.String(500), nullable=True),
        sa.Column("inicio_em", sa.DateTime(), nullable=False),
        sa.Column("fim_em", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="rascunho"),
        sa.Column("criado_por_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revisado_por_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revisado_em", sa.DateTime(), nullable=True),
        sa.Column("motivo_revisao", sa.String(400), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organizacao_id", "codigo", name="uq_campanha_org_codigo"),
        sa.CheckConstraint("status IN ('rascunho','em_revisao','aprovada','rejeitada','cancelada')", name="ck_campanha_status"),
    )
    op.create_index("ix_campanhas_comerciais_organizacao_id", "campanhas_comerciais", ["organizacao_id"])
    op.create_table(
        "campanhas_comerciais_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campanha_id", sa.Integer(), sa.ForeignKey("campanhas_comerciais.id", ondelete="CASCADE"), nullable=False),
        sa.Column("preco_id", sa.Integer(), sa.ForeignKey("precos.id", ondelete="RESTRICT"), nullable=False),
        sa.UniqueConstraint("campanha_id", "preco_id", name="uq_campanha_preco"),
    )
    op.create_index("ix_campanhas_comerciais_itens_campanha_id", "campanhas_comerciais_itens", ["campanha_id"])
    op.create_index("ix_campanhas_comerciais_itens_preco_id", "campanhas_comerciais_itens", ["preco_id"])


def downgrade():
    # Não altera ofertas preexistentes. Preservar auditoria da campanha antes do rollback.
    op.drop_table("campanhas_comerciais_itens")
    op.drop_table("campanhas_comerciais")
    op.drop_table("importacoes_catalogo")
