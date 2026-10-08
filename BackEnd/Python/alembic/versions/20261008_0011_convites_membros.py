"""Fase 2C: convites organizacionais e auditoria de membros.

Revision ID: 20261008_0011
Revises: 20261008_0010
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0011"
down_revision = "20261008_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "convites_organizacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(160), nullable=False),
        sa.Column("papel", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("criado_por_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("usado_em", sa.DateTime(), nullable=True),
        sa.Column("revogado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("papel IN ('proprietario','gestor','editor','leitor')", name="ck_convite_org_papel"),
    )
    op.create_index("ix_convites_organizacao_organizacao_id", "convites_organizacao", ["organizacao_id"])
    op.create_index("ix_convites_organizacao_token_hash", "convites_organizacao", ["token_hash"], unique=True)
    op.create_index("ix_convite_org_org_email", "convites_organizacao", ["organizacao_id", "email"])
    op.create_table(
        "auditoria_organizacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("autor_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("acao", sa.String(60), nullable=False),
        sa.Column("alvo_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("detalhes", sa.JSON(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auditoria_organizacao_organizacao_id", "auditoria_organizacao", ["organizacao_id"])


def downgrade():
    # A operação descarta convites pendentes e auditoria. Backup antes de rollback real.
    op.drop_table("auditoria_organizacao")
    op.drop_index("ix_convite_org_org_email", table_name="convites_organizacao")
    op.drop_index("ix_convites_organizacao_token_hash", table_name="convites_organizacao")
    op.drop_index("ix_convites_organizacao_organizacao_id", table_name="convites_organizacao")
    op.drop_table("convites_organizacao")
