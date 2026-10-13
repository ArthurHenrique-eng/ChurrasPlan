"""Periodicidade para assinaturas B2B de teste.

Revision ID: 20261008_0016
Revises: 20261008_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0016"
down_revision = "20261008_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assinaturas_organizacao", sa.Column("periodicidade", sa.String(10),
                                                        nullable=False, server_default="mensal"))
    op.add_column("tentativas_checkout", sa.Column("periodicidade", sa.String(10),
                                                  nullable=False, server_default="mensal"))


def downgrade():
    op.drop_column("tentativas_checkout", "periodicidade")
    op.drop_column("assinaturas_organizacao", "periodicidade")
