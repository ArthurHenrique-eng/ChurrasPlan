"""Contexto pseudônimo mínimo para funis consultáveis.

Adiciona duas colunas nullable e índice por tipo/período/contexto/evento. Não
reconstitui sessões nem vincula eventos legados a usuários. Nenhuma PII ou
identificador bruto é persistido; B2C usa HMAC de sessão por dia, B2B de tenant.
Compatível com os registros existentes. Downgrade remove apenas as novas
colunas/índice, preservando todos os eventos. Validar Alembic/MySQL e schema.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261012_0024"
down_revision = "20261012_0023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("eventos_produto", sa.Column("contexto_tipo", sa.String(20), nullable=True))
    op.add_column("eventos_produto", sa.Column("contexto_hash", sa.String(64), nullable=True))
    op.create_index("ix_eventos_produto_funil", "eventos_produto", ["contexto_tipo", "criado_em", "contexto_hash", "evento"])


def downgrade():
    op.drop_index("ix_eventos_produto_funil", table_name="eventos_produto")
    op.drop_column("eventos_produto", "contexto_hash")
    op.drop_column("eventos_produto", "contexto_tipo")
