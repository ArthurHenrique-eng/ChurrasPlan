"""Fase 3: assinaturas B2B, tentativas idempotentes e registro de webhook.

Revision ID: 20261008_0014
Revises: 20261008_0013
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0014"
down_revision = "20261008_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assinaturas_organizacao",
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey("organizacoes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("stripe_customer_id", sa.String(100), unique=True),
        sa.Column("stripe_subscription_id", sa.String(100), unique=True),
        sa.Column("plano_slug", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(30), nullable=False, server_default="sem_assinatura"),
        sa.Column("periodo_fim_em", sa.DateTime()),
        sa.Column("tolerancia_ate", sa.DateTime()),
        sa.Column("cancelamento_agendado", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("sincronizado_em", sa.DateTime()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "tentativas_checkout",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("chave_idempotencia", sa.String(80), nullable=False),
        sa.Column("plano_slug", sa.String(20), nullable=False),
        sa.Column("stripe_session_id", sa.String(130), nullable=False, unique=True),
        sa.Column("stripe_subscription_id", sa.String(100)),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organizacao_id", "chave_idempotencia", name="uq_checkout_org_chave"),
    )
    op.create_index("ix_tentativas_checkout_organizacao_id", "tentativas_checkout", ["organizacao_id"])
    op.create_table(
        "eventos_billing",
        sa.Column("event_id", sa.String(130), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey("organizacoes.id", ondelete="SET NULL")),
        sa.Column("resultado", sa.String(40), nullable=False),
        sa.Column("registrado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    # Descarta histórico de cobranças! Backup + conciliação antes de reverter.
    op.drop_table("eventos_billing")
    op.drop_table("tentativas_checkout")
    op.drop_table("assinaturas_organizacao")
