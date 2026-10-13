"""Concessões B2B administrativas sem integração de cobrança.

Revision ID: 20261008_0010
Revises: 20261008_0009

A ausência de concessão implica sempre Free; nenhuma conta legada recebe
automaticamente Pro ou Business. Não há alteração no cálculo B2C.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0010"
down_revision = "20261008_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "concessoes_organizacao",
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey(
            "organizacoes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("plano_slug", sa.String(length=20), nullable=False),
        sa.Column("origem", sa.String(length=30), nullable=False,
                  server_default="cortesia_admin"),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("alterado_por_usuario_id", sa.Integer(),
                  sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("plano_slug IN ('pro', 'business')",
                           name="ck_concessao_plano_permitido"),
        sa.CheckConstraint("origem = 'cortesia_admin'",
                           name="ck_concessao_origem_administrativa"),
    )


def downgrade():
    # Aviso: apagar a tabela descarta concessões administrativas em vigor.
    # Manter backup antes de qualquer downgrade fora do CI.
    op.drop_table("concessoes_organizacao")
