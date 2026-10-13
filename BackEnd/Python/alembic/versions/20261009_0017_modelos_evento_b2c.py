"""Modelos pessoais Premium preservados mesmo quando o evento original é excluído.

Revision ID: 20261009_0017
Revises: 20261008_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0017"
down_revision = "20261008_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "modelos_evento_usuario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("dados", sa.JSON(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_modelos_evento_usuario_usuario_id", "modelos_evento_usuario", ["usuario_id"])


def downgrade():
    # O rollback apaga SOMENTE os modelos, não os eventos ou assinaturas.
    # O índice de usuario_id sustenta a FK no MySQL: a tabela deve cair inteira,
    # sem tentar remover antes o índice usado pela restrição referencial.
    op.drop_table("modelos_evento_usuario")
