'Consumo diário do assistente. Chave composta serializada por usuário. Não persiste prompts ou segredos; rollback remove somente contadores.'
from alembic import op
import sqlalchemy as sa

revision = '20261012_0021'
down_revision = '20261012_0020'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('consumo_assistente',
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('dia', sa.String(length=10), primary_key=True, nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False, server_default='0'))

def downgrade():
    op.drop_table('consumo_assistente')
