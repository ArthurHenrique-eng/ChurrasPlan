"""Identidade pelo Neon Auth (login gerenciado).

Adiciona `usuarios.neon_auth_user_id` (UUID do usuário em neon_auth."user",
único e opcional) e torna `usuarios.senha_hash` opcional, porque contas
criadas pelo Neon Auth não têm senha local. Nenhum dado é apagado: contas
antigas mantêm o hash e continuam funcionando com AUTH_PROVIDER=local.

Downgrade remove a coluna nova e volta `senha_hash` a obrigatória; contas sem
senha local recebem um marcador que nunca confere com senha alguma.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261127_0025"
down_revision = "20261012_0024"
branch_labels = None
depends_on = None

MARCADOR_SEM_SENHA = "!neon-auth"


def upgrade():
    op.add_column("usuarios", sa.Column("neon_auth_user_id", sa.String(36), nullable=True))
    op.create_index("ix_usuarios_neon_auth_user_id", "usuarios", ["neon_auth_user_id"], unique=True)
    with op.batch_alter_table("usuarios") as tabela:
        tabela.alter_column("senha_hash", existing_type=sa.String(255), nullable=True)


def downgrade():
    usuarios = sa.table("usuarios", sa.column("senha_hash", sa.String(255)))
    op.execute(usuarios.update().where(usuarios.c.senha_hash.is_(None)).values(senha_hash=MARCADOR_SEM_SENHA))
    with op.batch_alter_table("usuarios") as tabela:
        tabela.alter_column("senha_hash", existing_type=sa.String(255), nullable=False)
    op.drop_index("ix_usuarios_neon_auth_user_id", table_name="usuarios")
    op.drop_column("usuarios", "neon_auth_user_id")
