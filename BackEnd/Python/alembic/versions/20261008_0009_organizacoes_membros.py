"""Estrutura multi-tenant inicial e migração conservadora de parceiros.

Revision ID: 20261008_0009
Revises: 20260925_0008

Preserva usuario_responsavel_id, preços, SKUs, IDs de estabelecimentos e o
histórico de planejamento. Admin / estabelecimentos sem proprietário ficam
sem organização, em vez de receber associação presumida.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0009"
down_revision = "20260925_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_organizacoes_slug", "organizacoes", ["slug"], unique=True)

    op.create_table(
        "organizacao_membros",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organizacao_id", sa.Integer(), sa.ForeignKey("organizacoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("papel", sa.String(length=20), server_default="leitor", nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organizacao_id", "usuario_id", name="uq_organizacao_membro"),
    )
    op.create_index("ix_organizacao_membros_organizacao_id", "organizacao_membros", ["organizacao_id"])
    op.create_index("ix_organizacao_membros_usuario_id", "organizacao_membros", ["usuario_id"])

    op.add_column("estabelecimentos", sa.Column("organizacao_id", sa.Integer(), nullable=True))
    op.create_index("ix_estabelecimentos_organizacao_id", "estabelecimentos", ["organizacao_id"])
    op.create_foreign_key(
        "fk_estabelecimentos_organizacao_id", "estabelecimentos", "organizacoes",
        ["organizacao_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column("produtos", sa.Column("organizacao_id", sa.Integer(), nullable=True))
    op.create_index("ix_produtos_organizacao_id", "produtos", ["organizacao_id"])
    op.create_foreign_key(
        "fk_produtos_organizacao_id", "produtos", "organizacoes",
        ["organizacao_id"], ["id"], ondelete="SET NULL",
    )

    conn = op.get_bind()
    usuarios = conn.execute(sa.text("""
        SELECT id, nome FROM usuarios
        WHERE papel = 'parceiro'
           OR id IN (
               SELECT DISTINCT usuario_responsavel_id FROM estabelecimentos
               WHERE usuario_responsavel_id IS NOT NULL
           )
        ORDER BY id
    """)).mappings().all()
    for usuario in usuarios:
        uid = int(usuario["id"])
        # Slug determinístico: migration reexecutada não cria organizações duplicadas.
        slug = f"legado-parceiro-{uid}"
        conn.execute(
            sa.text("INSERT INTO organizacoes (slug, nome, ativo) VALUES (:slug, :nome, 1)"),
            {"slug": slug, "nome": (str(usuario["nome"])[:125] + " - Parceiro")},
        )
        oid = conn.execute(
            sa.text("SELECT id FROM organizacoes WHERE slug = :slug"), {"slug": slug}
        ).scalar_one()
        conn.execute(
            sa.text("""
                INSERT INTO organizacao_membros (organizacao_id, usuario_id, papel, ativo)
                VALUES (:oid, :uid, 'proprietario', 1)
            """), {"oid": oid, "uid": uid},
        )
        conn.execute(
            sa.text("""
                UPDATE estabelecimentos SET organizacao_id = :oid
                WHERE usuario_responsavel_id = :uid AND organizacao_id IS NULL
            """), {"oid": oid, "uid": uid},
        )

    # SKUs comerciais legados associados a ofertas de uma única organização.
    # SKUs sem oferta ou compartilhados entre organizações ficam globais (NULL)
    # para não atribuir propriedade sem evidência.
    associados = conn.execute(sa.text("""
        SELECT p.id AS produto_id, MIN(e.organizacao_id) AS organizacao_id
        FROM produtos p
        JOIN precos pr ON pr.produto_id = p.id
        JOIN estabelecimentos e ON e.id = pr.estabelecimento_id
        WHERE p.tipo_produto = 'comercial'
        GROUP BY p.id
        HAVING COUNT(DISTINCT e.organizacao_id) = 1
           AND SUM(CASE WHEN e.organizacao_id IS NULL THEN 1 ELSE 0 END) = 0
    """)).mappings().all()
    for item in associados:
        conn.execute(
            sa.text("UPDATE produtos SET organizacao_id=:org WHERE id=:pid"),
            {"org": int(item["organizacao_id"]), "pid": int(item["produto_id"])},
        )


def downgrade() -> None:
    # As chaves legadas de proprietários e ofertas continuam preservadas.
    op.drop_constraint("fk_produtos_organizacao_id", "produtos", type_="foreignkey")
    op.drop_index("ix_produtos_organizacao_id", table_name="produtos")
    op.drop_column("produtos", "organizacao_id")
    op.drop_constraint("fk_estabelecimentos_organizacao_id", "estabelecimentos", type_="foreignkey")
    op.drop_index("ix_estabelecimentos_organizacao_id", table_name="estabelecimentos")
    op.drop_column("estabelecimentos", "organizacao_id")
    # MySQL exige índices de suporte enquanto as foreign keys da tabela
    # existem. DROP TABLE remove constraints + índices na ordem correta.
    op.drop_table("organizacao_membros")
    op.drop_table("organizacoes")
