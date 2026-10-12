"""EAN compartilhável entre empresas, único no catálogo de cada organização.

Preserva IDs, ofertas e EANs existentes. Troca índice global único por índice
de consulta e constraint por tenant. Rollback falha fechado se EANs já tiverem
sido compartilhados entre organizações; nunca apaga produtos para reverter.
"""
from alembic import op
import sqlalchemy as sa
revision = "20261012_0023"
down_revision = "20261012_0022"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_produtos_ean", table_name="produtos")
    op.create_index("ix_produtos_ean", "produtos", ["ean"])
    op.create_unique_constraint("uq_produto_org_ean", "produtos", ["organizacao_id", "ean"])


def downgrade():
    existe = op.get_bind().execute(sa.text("SELECT ean FROM produtos WHERE ean IS NOT NULL GROUP BY ean HAVING COUNT(*) > 1 LIMIT 1")).first()
    if existe:
        raise RuntimeError("Rollback bloqueado: EAN compartilhado entre organizações. Planeje migração sem perda de dados.")
    op.drop_constraint("uq_produto_org_ean", "produtos", type_="unique")
    op.drop_index("ix_produtos_ean", table_name="produtos")
    op.create_index("ix_produtos_ean", "produtos", ["ean"], unique=True)
