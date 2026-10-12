'Growth: dados mínimos, consentimento separado e índices de funil. Rollback apaga somente novos registros; exportar antes de reverter.'
from alembic import op
import sqlalchemy as sa

revision = '20261012_0019'
down_revision = '20261012_0018'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('leads_comerciais',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('nome', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=160), nullable=False),
        sa.Column('empresa', sa.String(length=150), nullable=False),
        sa.Column('tipo_estabelecimento', sa.String(length=40), nullable=False),
        sa.Column('cidade', sa.String(length=120), nullable=False),
        sa.Column('origem', sa.String(length=60), nullable=False, server_default='parceiros'),
        sa.Column('utm', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='novo'),
        sa.Column('marketing_concedido', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('marketing_revogado_em', sa.DateTime(), nullable=True),
        sa.Column('descadastro_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('privacidade_versao', sa.String(length=40), nullable=False),
        sa.Column('organizacao_id', sa.Integer(), sa.ForeignKey('organizacoes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.create_index('ix_leads_comerciais_criado_em', 'leads_comerciais', ['criado_em'], unique=False)
    op.create_index('ix_leads_comerciais_email', 'leads_comerciais', ['email'], unique=False)
    op.create_index('ix_leads_comerciais_status', 'leads_comerciais', ['status'], unique=False)
    op.create_table('atividades_lead',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('leads_comerciais.id', ondelete='CASCADE'), nullable=False),
        sa.Column('admin_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('tipo', sa.String(length=30), nullable=False),
        sa.Column('nota', sa.String(length=800), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.create_index('ix_atividades_lead_lead_id', 'atividades_lead', ['lead_id'], unique=False)
    op.create_table('eventos_produto',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('evento', sa.String(length=60), nullable=False),
        sa.Column('propriedades', sa.JSON(), nullable=False),
        sa.Column('dedup_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.create_index('ix_eventos_produto_criado_em', 'eventos_produto', ['criado_em'], unique=False)
    op.create_index('ix_eventos_produto_evento', 'eventos_produto', ['evento'], unique=False)
    op.create_table('indicacoes_usuario',
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('codigo', sa.String(length=48), nullable=False, unique=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.create_table('atribuicoes_cadastro',
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('indicador_id', sa.Integer(), sa.ForeignKey('usuarios.id', ondelete='SET NULL'), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.create_index('ix_atribuicoes_cadastro_indicador_id', 'atribuicoes_cadastro', ['indicador_id'], unique=False)
    op.create_table('feedback_parceiro',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('organizacao_id', sa.Integer(), sa.ForeignKey('organizacoes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nota', sa.Integer(), nullable=False),
        sa.Column('comentario', sa.String(length=800), nullable=True),
        sa.Column('disposicao_pagar', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.create_index('ix_feedback_parceiro_organizacao_id', 'feedback_parceiro', ['organizacao_id'], unique=False)
    op.create_table('custos_operacao',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('competencia', sa.String(length=7), nullable=False),
        sa.Column('categoria', sa.String(length=30), nullable=False),
        sa.Column('valor', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.create_index('ix_custos_operacao_competencia', 'custos_operacao', ['competencia'], unique=False)

def downgrade():
    op.drop_table('custos_operacao')
    op.drop_table('feedback_parceiro')
    op.drop_table('atribuicoes_cadastro')
    op.drop_table('indicacoes_usuario')
    op.drop_table('eventos_produto')
    op.drop_table('atividades_lead')
    op.drop_table('leads_comerciais')
