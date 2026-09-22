"""Production readiness: LGPD, segurança e auditoria administrativa.

- consentimentos legais versionados;
- eventos de segurança com chave HMAC para rate limiting;
- auditoria de ações administrativas;
- remoção do IP bruto legado das sessões e substituição por hash.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0005"
down_revision = "20260918_0004"
branch_labels = None
depends_on = None


def _tables(bind):
    return set(sa.inspect(bind).get_table_names())


def _cols(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table):
    return {i.get("name") for i in sa.inspect(bind).get_indexes(table)}


def upgrade():
    bind = op.get_bind()
    tables = _tables(bind)

    if "consentimentos_usuario" not in tables:
        op.create_table(
            "consentimentos_usuario",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("usuario_id", sa.Integer(), nullable=False),
            sa.Column("tipo", sa.String(30), nullable=False),
            sa.Column("versao", sa.String(30), nullable=False),
            sa.Column("concedido", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("origem", sa.String(40), nullable=False, server_default="cadastro"),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE", name="fk_consentimentos_usuario_usuario"),
            sa.UniqueConstraint("usuario_id", "tipo", "versao", name="uq_consentimento_usuario_tipo_versao"),
        )
        op.create_index("ix_consentimentos_usuario_usuario_id", "consentimentos_usuario", ["usuario_id"])
        op.create_index("ix_consentimentos_usuario_tipo", "consentimentos_usuario", ["tipo"])

    tables = _tables(bind)
    if "eventos_seguranca" not in tables:
        op.create_table(
            "eventos_seguranca",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tipo", sa.String(40), nullable=False),
            sa.Column("chave_hash", sa.String(64), nullable=False),
            sa.Column("sucesso", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_eventos_seguranca_tipo", "eventos_seguranca", ["tipo"])
        op.create_index("ix_eventos_seguranca_chave_hash", "eventos_seguranca", ["chave_hash"])
        op.create_index("ix_eventos_seguranca_criado_em", "eventos_seguranca", ["criado_em"])
        op.create_index("ix_eventos_seguranca_tipo_chave_criado", "eventos_seguranca", ["tipo", "chave_hash", "criado_em"])

    tables = _tables(bind)
    if "auditoria_admin" not in tables:
        op.create_table(
            "auditoria_admin",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("admin_usuario_id", sa.Integer(), nullable=True),
            sa.Column("acao", sa.String(80), nullable=False),
            sa.Column("entidade", sa.String(60), nullable=False),
            sa.Column("entidade_id", sa.String(80), nullable=True),
            sa.Column("detalhes", sa.JSON(), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["admin_usuario_id"], ["usuarios.id"], ondelete="SET NULL", name="fk_auditoria_admin_usuario"),
        )
        op.create_index("ix_auditoria_admin_admin_usuario_id", "auditoria_admin", ["admin_usuario_id"])
        op.create_index("ix_auditoria_admin_acao", "auditoria_admin", ["acao"])
        op.create_index("ix_auditoria_admin_entidade", "auditoria_admin", ["entidade"])
        op.create_index("ix_auditoria_admin_criado_em", "auditoria_admin", ["criado_em"])
        op.create_index("ix_auditoria_admin_entidade_id_criado", "auditoria_admin", ["entidade", "entidade_id", "criado_em"])

    # Migra sessões antigas apagando IP bruto. Não tentamos reidentificar nem
    # converter o dado legado; o novo hash é criado somente em sessões futuras.
    cols = _cols(bind, "sessoes_usuario")
    if "ip_hash" not in cols:
        op.add_column("sessoes_usuario", sa.Column("ip_hash", sa.String(64), nullable=True))
    cols = _cols(bind, "sessoes_usuario")
    if "ip_criado" in cols:
        with op.batch_alter_table("sessoes_usuario") as batch:
            batch.drop_column("ip_criado")


def downgrade():
    bind = op.get_bind()
    tables = _tables(bind)
    if "sessoes_usuario" in tables and "ip_hash" in _cols(bind, "sessoes_usuario"):
        with op.batch_alter_table("sessoes_usuario") as batch:
            batch.drop_column("ip_hash")
            batch.add_column(sa.Column("ip_criado", sa.String(64), nullable=True))
    for table in ["auditoria_admin", "eventos_seguranca", "consentimentos_usuario"]:
        if table in _tables(bind):
            op.drop_table(table)
