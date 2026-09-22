"""Restaura defaults de timestamps em usuarios.

Revision ID: 20260922_0006
Revises: 20260918_0005
"""

from alembic import op
import sqlalchemy as sa


revision = "20260922_0006"
down_revision = "20260918_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usuarios") as batch:
        batch.alter_column(
            "criado_em",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )

        batch.alter_column(
            "atualizado_em",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )


def downgrade() -> None:
    with op.batch_alter_table("usuarios") as batch:
        batch.alter_column(
            "criado_em",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            nullable=False,
            server_default=None,
        )

        batch.alter_column(
            "atualizado_em",
            existing_type=sa.DateTime(),
            existing_nullable=False,
            nullable=False,
            server_default=None,
        )