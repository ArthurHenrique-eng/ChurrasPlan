'Clientes, propostas com snapshot e retenção solicitada. Índices de titularidade e chave única por usuário. Não altera os cálculos; rollback remove somente os novos dados.'
from alembic import op
import sqlalchemy as sa

revision = '20261012_0020'
down_revision = '20261012_0019'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('clientes_profissionais',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=160), nullable=True),
        sa.Column('telefone', sa.String(length=30), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.create_index('ix_clientes_profissionais_usuario_id', 'clientes_profissionais', ['usuario_id'], unique=False)
    op.create_table('propostas_profissionais',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cliente_id', sa.Integer(), sa.ForeignKey('clientes_profissionais.id', ondelete='SET NULL'), nullable=True),
        sa.Column('churrasco_id', sa.Integer(), sa.ForeignKey('churrascos.id', ondelete='SET NULL'), nullable=True),
        sa.Column('chave', sa.String(length=80), nullable=False),
        sa.Column('titulo', sa.String(length=150), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('custo_estimado', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('preco_proposto', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='rascunho'),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('usuario_id','chave',name='uq_proposta_usuario_chave'))
    op.create_index('ix_propostas_profissionais_usuario_id', 'propostas_profissionais', ['usuario_id'], unique=False)
    op.create_table('favoritos_estabelecimentos',
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('estabelecimento_id', sa.Integer(), sa.ForeignKey('estabelecimentos.id', ondelete='CASCADE'), primary_key=True, nullable=False))
    op.create_table('lembretes_evento',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), nullable=False),
        sa.Column('churrasco_id', sa.Integer(), sa.ForeignKey('churrascos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tarefa_id', sa.Integer(), sa.ForeignKey('tarefas_outbox.id', ondelete='SET NULL'), nullable=True),
        sa.Column('quando', sa.DateTime(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.create_index('ix_lembretes_evento_usuario_id', 'lembretes_evento', ['usuario_id'], unique=False)

def downgrade():
    op.drop_table('lembretes_evento')
    op.drop_table('favoritos_estabelecimentos')
    op.drop_table('propostas_profissionais')
    op.drop_table('clientes_profissionais')
