"""MFA, limites HTTP compartilhados e outbox durável.

Preserva usuários/sessões, acrescenta verificação MFA nullable.
Rollback remove novos dados operacionais: exportar antes de reverter.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261012_0018"
down_revision = "20261009_0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sessoes_usuario", sa.Column("mfa_verificado_em", sa.DateTime(), nullable=True))
    op.create_table("credenciais_mfa",
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("segredo_cifrado", sa.Text(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("ultimo_passo", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_table("recuperacao_mfa",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("usado_em", sa.DateTime(), nullable=True))
    op.create_index("ix_recuperacao_mfa_usuario_id", "recuperacao_mfa", ["usuario_id"])
    op.create_table("contadores_requisicao",
        sa.Column("chave", sa.String(64), primary_key=True),
        sa.Column("janela", sa.Integer(), primary_key=True),
        sa.Column("quantidade", sa.Integer(), nullable=False))
    op.create_table("tarefas_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("chave", sa.String(120), nullable=False, unique=True),
        sa.Column("payload_cifrado", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pendente"),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disponivel_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("lease_ate", sa.DateTime(), nullable=True),
        sa.Column("lease_token", sa.String(64), nullable=True),
        sa.Column("erro_tipo", sa.String(80), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("concluido_em", sa.DateTime(), nullable=True))
    op.create_index("ix_outbox_pronta", "tarefas_outbox", ["status", "disponivel_em"])
    op.create_table("estado_worker",
        sa.Column("nome", sa.String(80), primary_key=True),
        sa.Column("heartbeat_em", sa.DateTime(), nullable=False))


def downgrade():
    for tabela in ("estado_worker", "tarefas_outbox", "contadores_requisicao", "recuperacao_mfa", "credenciais_mfa"):
        op.drop_table(tabela)
    op.drop_column("sessoes_usuario", "mfa_verificado_em")
