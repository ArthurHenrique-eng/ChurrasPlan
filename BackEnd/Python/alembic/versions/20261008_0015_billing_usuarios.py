"""Assinaturas Premium B2C isoladas do billing B2B.

Revision ID: 20261008_0015
Revises: 20261008_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0015"
down_revision = "20261008_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assinaturas_stripe_usuario",
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("stripe_customer_id", sa.String(100), unique=True),
        sa.Column("stripe_subscription_id", sa.String(100), unique=True),
        sa.Column("plano_slug", sa.String(30), nullable=False, server_default="free"),
        sa.Column("periodicidade", sa.String(10), nullable=False, server_default="mensal"),
        sa.Column("status", sa.String(30), nullable=False, server_default="sem_assinatura"),
        sa.Column("periodo_fim_em", sa.DateTime()),
        sa.Column("cancelamento_agendado", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("sincronizado_em", sa.DateTime()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "tentativas_checkout_usuario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chave_idempotencia", sa.String(80), nullable=False),
        sa.Column("plano_slug", sa.String(30), nullable=False),
        sa.Column("periodicidade", sa.String(10), nullable=False),
        sa.Column("stripe_session_id", sa.String(130), nullable=False, unique=True),
        sa.Column("stripe_subscription_id", sa.String(100), unique=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("usuario_id", "chave_idempotencia", name="uq_checkout_usuario_chave"),
    )
    op.create_index("ix_tentativas_checkout_usuario_usuario_id", "tentativas_checkout_usuario", ["usuario_id"])


def downgrade():
    op.drop_table("tentativas_checkout_usuario")
    op.drop_table("assinaturas_stripe_usuario")
