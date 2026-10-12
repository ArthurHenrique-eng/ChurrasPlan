"""Titularidade da outbox e deduplicação de interações comerciais.

Novas colunas nullable preservam eventos legados. Índice único evita replay;
FK permite apagar tarefas pessoais junto da conta. Rollback remove apenas
colunas novas e sua rastreabilidade, preservando tarefas e métricas.
"""
from alembic import op
import sqlalchemy as sa
revision = "20261012_0022"
down_revision = "20261012_0021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tarefas_outbox", sa.Column("usuario_id", sa.Integer(), nullable=True))
    op.create_index("ix_tarefas_outbox_usuario_id", "tarefas_outbox", ["usuario_id"])
    op.create_foreign_key("fk_outbox_usuario", "tarefas_outbox", "usuarios", ["usuario_id"], ["id"], ondelete="CASCADE")
    op.add_column("metricas_estabelecimentos", sa.Column("dedup_hash", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_metricas_dedup", "metricas_estabelecimentos", ["dedup_hash"])


def downgrade():
    op.drop_constraint("uq_metricas_dedup", "metricas_estabelecimentos", type_="unique")
    op.drop_column("metricas_estabelecimentos", "dedup_hash")
    op.drop_constraint("fk_outbox_usuario", "tarefas_outbox", type_="foreignkey")
    op.drop_index("ix_tarefas_outbox_usuario_id", table_name="tarefas_outbox")
    op.drop_column("tarefas_outbox", "usuario_id")
