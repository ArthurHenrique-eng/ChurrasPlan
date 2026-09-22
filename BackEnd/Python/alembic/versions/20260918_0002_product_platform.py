"""Fases 3-6: contas, orçamento, RSVP, SKU, parceiros e compra real.

A migration é aditiva e tolerante ao schema v0.2. Bancos vazios podem já ter
recebido as tabelas atuais pela migration baseline; nesse caso as operações
abaixo tornam-se no-op por inspeção.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_0002"
down_revision = "20260917_0001"
branch_labels = None
depends_on = None


def _cols(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _add(bind, table, column):
    if column.name not in _cols(bind, table):
        op.add_column(table, column)


def _index_names(bind, table):
    return {i.get("name") for i in sa.inspect(bind).get_indexes(table)}


def _idx(bind, name, table, cols, unique=False):
    if name not in _index_names(bind, table):
        op.create_index(name, table, cols, unique=unique)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # Tabelas introduzidas por esta revisão são declaradas explicitamente aqui.
    # Migrations são snapshots históricos e não podem depender do Base.metadata
    # atual, que continuará evoluindo depois desta release.
    if "sessoes_usuario" not in tables:
        op.create_table(
            "sessoes_usuario",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("usuario_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("csrf_hash", sa.String(64), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("ultimo_uso_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("expira_em", sa.DateTime(), nullable=False),
            sa.Column("revogada", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("user_agent", sa.String(255), nullable=True),
            sa.Column("ip_criado", sa.String(64), nullable=True),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        )
    if "tokens_usuario" not in tables:
        op.create_table(
            "tokens_usuario",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("usuario_id", sa.Integer(), nullable=False),
            sa.Column("tipo", sa.String(30), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("expira_em", sa.DateTime(), nullable=False),
            sa.Column("usado_em", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        )
    if "convites_churrasco" not in tables:
        op.create_table(
            "convites_churrasco",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("churrasco_id", sa.Integer(), nullable=False),
            sa.Column("codigo", sa.String(32), nullable=False),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("expira_em", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["churrasco_id"], ["churrascos.id"], ondelete="CASCADE"),
        )
    if "respostas_convite" not in tables:
        op.create_table(
            "respostas_convite",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("convite_id", sa.Integer(), nullable=False),
            sa.Column("chave_resposta", sa.String(48), nullable=False),
            sa.Column("nome", sa.String(120), nullable=False),
            sa.Column("resposta", sa.String(20), nullable=False),
            sa.Column("tipo_convidado", sa.String(20), nullable=False, server_default="adulto"),
            sa.Column("consome_alcool", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("vegetariano", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("vegano", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sem_carne_bovina", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sem_carne_suina", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("intolerante_lactose", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("alergias", sa.Text(), nullable=True),
            sa.Column("outras_restricoes", sa.Text(), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["convite_id"], ["convites_churrasco.id"], ondelete="CASCADE"),
        )
    if "planos_assinatura" not in tables:
        op.create_table(
            "planos_assinatura",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(50), nullable=False),
            sa.Column("nome", sa.String(100), nullable=False),
            sa.Column("publico_alvo", sa.String(20), nullable=False, server_default="usuario"),
            sa.Column("preco_mensal", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("recursos", sa.JSON(), nullable=True),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
    if "assinaturas_usuario" not in tables:
        op.create_table(
            "assinaturas_usuario",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("usuario_id", sa.Integer(), nullable=False),
            sa.Column("plano_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="ativa"),
            sa.Column("provedor", sa.String(40), nullable=True),
            sa.Column("id_externo", sa.String(120), nullable=True),
            sa.Column("iniciado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("termina_em", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["plano_id"], ["planos_assinatura.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint("id_externo"),
        )

    # Índices definidos pelos models desta revisão, também congelados aqui.
    for name, table, cols, unique in [
        ("ix_sessoes_usuario_usuario_id", "sessoes_usuario", ["usuario_id"], False),
        ("ix_sessoes_usuario_token_hash", "sessoes_usuario", ["token_hash"], True),
        ("ix_sessoes_usuario_expira_em", "sessoes_usuario", ["expira_em"], False),
        ("ix_tokens_usuario_usuario_id", "tokens_usuario", ["usuario_id"], False),
        ("ix_tokens_usuario_tipo", "tokens_usuario", ["tipo"], False),
        ("ix_tokens_usuario_token_hash", "tokens_usuario", ["token_hash"], True),
        ("ix_convites_churrasco_churrasco_id", "convites_churrasco", ["churrasco_id"], True),
        ("ix_convites_churrasco_codigo", "convites_churrasco", ["codigo"], True),
        ("ix_respostas_convite_convite_id", "respostas_convite", ["convite_id"], False),
        ("ix_respostas_convite_chave_resposta", "respostas_convite", ["chave_resposta"], True),
        ("ix_respostas_convite_resposta", "respostas_convite", ["resposta"], False),
        ("ix_planos_assinatura_slug", "planos_assinatura", ["slug"], True),
        ("ix_assinaturas_usuario_usuario_id", "assinaturas_usuario", ["usuario_id"], False),
    ]:
        _idx(bind, name, table, cols, unique=unique)
    inspector = sa.inspect(bind)

    # Usuários
    for c in [
        sa.Column("papel", sa.String(20), nullable=False, server_default="usuario"),
        sa.Column("plano", sa.String(30), nullable=False, server_default="gratuito"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_verificado_em", sa.DateTime(), nullable=True),
        sa.Column("ultimo_login_em", sa.DateTime(), nullable=True),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
    ]: _add(bind, "usuarios", c)
    bind.execute(sa.text("UPDATE usuarios SET atualizado_em=COALESCE(atualizado_em, criado_em, CURRENT_TIMESTAMP)"))

    # Churrascos
    for c in [
        sa.Column("status", sa.String(20), nullable=False, server_default="rascunho"),
        sa.Column("data_evento", sa.DateTime(), nullable=True),
        sa.Column("adultos", sa.Integer(), nullable=True),
        sa.Column("adultos_bebem_alcool", sa.Integer(), nullable=True),
        sa.Column("vegetarianos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("veganos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sem_carne_bovina", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sem_carne_suina", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("intolerantes_lactose", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alergias", sa.Text(), nullable=True),
        sa.Column("outras_restricoes", sa.Text(), nullable=True),
        sa.Column("orcamento_maximo", sa.Numeric(12,2), nullable=True),
        sa.Column("dividir_entre", sa.Integer(), nullable=True),
    ]: _add(bind, "churrascos", c)
    bind.execute(sa.text("UPDATE churrascos SET adultos=COALESCE(adultos, homens + mulheres), adultos_bebem_alcool=COALESCE(adultos_bebem_alcool, homens_bebem_alcool + mulheres_bebem_alcool)"))

    # Produtos comerciais / SKU
    for c in [
        sa.Column("produto_pai_id", sa.Integer(), nullable=True),
        sa.Column("tipo_produto", sa.String(20), nullable=False, server_default="generico"),
        sa.Column("marca", sa.String(100), nullable=True),
        sa.Column("variante", sa.String(120), nullable=True),
        sa.Column("fabricante", sa.String(120), nullable=True),
        sa.Column("ean", sa.String(32), nullable=True),
        sa.Column("sku", sa.String(80), nullable=True),
    ]: _add(bind, "produtos", c)
    if bind.dialect.name == "mysql":
        fks = {fk.get("name") for fk in sa.inspect(bind).get_foreign_keys("produtos")}
        if "fk_produtos_produto_pai" not in fks:
            op.create_foreign_key("fk_produtos_produto_pai", "produtos", "produtos", ["produto_pai_id"], ["id"], ondelete="SET NULL")
    _idx(bind, "ix_produtos_produto_pai_id", "produtos", ["produto_pai_id"])
    _idx(bind, "ix_produtos_tipo_produto", "produtos", ["tipo_produto"])
    _idx(bind, "ix_produtos_marca", "produtos", ["marca"])
    _idx(bind, "ix_produtos_ean", "produtos", ["ean"], unique=True)

    # Estabelecimentos / parceiro / localização
    for c in [
        sa.Column("usuario_responsavel_id", sa.Integer(), nullable=True),
        sa.Column("logradouro", sa.String(160), nullable=True), sa.Column("numero", sa.String(30), nullable=True),
        sa.Column("bairro", sa.String(100), nullable=True), sa.Column("cidade", sa.String(100), nullable=True),
        sa.Column("estado", sa.String(2), nullable=True), sa.Column("cep", sa.String(12), nullable=True),
        sa.Column("google_place_id", sa.String(255), nullable=True), sa.Column("avaliacao", sa.Numeric(3,2), nullable=True),
        sa.Column("quantidade_avaliacoes", sa.Integer(), nullable=True),
        sa.Column("parceiro_verificado", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]: _add(bind, "estabelecimentos", c)
    if bind.dialect.name == "mysql":
        fks = {fk.get("name") for fk in sa.inspect(bind).get_foreign_keys("estabelecimentos")}
        if "fk_estabelecimentos_usuario_responsavel" not in fks:
            op.create_foreign_key("fk_estabelecimentos_usuario_responsavel", "estabelecimentos", "usuarios", ["usuario_responsavel_id"], ["id"], ondelete="SET NULL")
    _idx(bind, "ix_estabelecimentos_usuario_responsavel_id", "estabelecimentos", ["usuario_responsavel_id"])
    _idx(bind, "ix_estabelecimentos_cidade", "estabelecimentos", ["cidade"])
    _idx(bind, "ix_estabelecimentos_estado", "estabelecimentos", ["estado"])
    _idx(bind, "ix_estabelecimentos_google_place_id", "estabelecimentos", ["google_place_id"], unique=True)

    # Ofertas do parceiro
    for c in [
        sa.Column("criado_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("preco_original", sa.Numeric(12,2), nullable=True),
        sa.Column("moeda", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("origem", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("estoque_status", sa.String(30), nullable=False, server_default="disponivel"),
        sa.Column("inicio_validade", sa.DateTime(), nullable=True),
        sa.Column("fim_validade", sa.DateTime(), nullable=True),
    ]: _add(bind, "precos", c)
    if bind.dialect.name == "mysql":
        fks = {fk.get("name") for fk in sa.inspect(bind).get_foreign_keys("precos")}
        if "fk_precos_criado_por_usuario" not in fks:
            op.create_foreign_key("fk_precos_criado_por_usuario", "precos", "usuarios", ["criado_por_usuario_id"], ["id"], ondelete="SET NULL")
    _idx(bind, "ix_precos_criado_por_usuario_id", "precos", ["criado_por_usuario_id"])

    # Checklist com gasto real
    for c in [
        sa.Column("estabelecimento_compra_id", sa.Integer(), nullable=True),
        sa.Column("valor_pago_total", sa.Numeric(12,2), nullable=True),
        sa.Column("comprado_em", sa.DateTime(), nullable=True),
    ]: _add(bind, "lista_compras_itens", c)
    if bind.dialect.name == "mysql":
        fks = {fk.get("name") for fk in sa.inspect(bind).get_foreign_keys("lista_compras_itens")}
        if "fk_lista_item_estabelecimento_compra" not in fks:
            op.create_foreign_key("fk_lista_item_estabelecimento_compra", "lista_compras_itens", "estabelecimentos", ["estabelecimento_compra_id"], ["id"], ondelete="SET NULL")

    # Planos básicos: arquitetura pronta para provedor de pagamento futuro.
    if "planos_assinatura" in sa.inspect(bind).get_table_names():
        existentes = {r[0] for r in bind.execute(sa.text("SELECT slug FROM planos_assinatura")).all()}
        if "gratuito" not in existentes:
            bind.execute(sa.text("INSERT INTO planos_assinatura (slug,nome,publico_alvo,preco_mensal,ativo) VALUES ('gratuito','Gratuito','usuario',0,1)"))
        if "parceiro" not in existentes:
            bind.execute(sa.text("INSERT INTO planos_assinatura (slug,nome,publico_alvo,preco_mensal,ativo) VALUES ('parceiro','Parceiro','parceiro',0,1)"))


def downgrade():
    # Reversão conservadora: remove tabelas novas. Colunas aditivas são mantidas
    # para evitar perda silenciosa de dados de conta/RSVP/preços reais.
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for name in ["assinaturas_usuario", "planos_assinatura", "respostas_convite", "convites_churrasco", "tokens_usuario", "sessoes_usuario"]:
        if name in tables:
            op.drop_table(name)
