"""Garante o catálogo base usado pelo planejador.

Revision ID: 20260925_0008
Revises: 20260925_0007

O catálogo principal não pode depender de seed_demo.py. Uma instalação criada
somente com `alembic upgrade head` precisa ter os produtos genéricos usados
pelos cálculos, pela área de parceiros e pelos preços de referência.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260925_0008"
down_revision = "20260925_0007"
branch_labels = None
depends_on = None


CATEGORIAS = [
    ("Carnes", "carne"),
    ("Bebidas", "bebida"),
    ("Extras", "extra"),
    ("Acompanhamentos", "acompanhamento"),
]


# slug, nome, categoria, unidade_consumo, unidade_venda,
# venda_fracionada, incremento_venda, quantidade_embalagem, unidade_embalagem
PRODUTOS = [
    ("picanha", "Picanha", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("picanha-suina", "Picanha suína", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("contra-file", "Contra-filé", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("alcatra", "Alcatra", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("fraldinha", "Fraldinha", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("maminha", "Maminha", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("acem", "Acém", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("costela", "Costela", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("costelinha-porco", "Costelinha de porco", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("cupim", "Cupim", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("linguica", "Linguiça", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("lombo", "Lombo", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("bisteca", "Bisteca", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("frango", "Frango", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("asinha-frango", "Asinha de frango", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("coracao", "Coração", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("queijo-coalho-churrasco", "Queijo coalho", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("pao-alho-churrasco", "Pão de alho", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("bife-ancho", "Bife Ancho", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("bife-chorizo", "Bife de Chorizo", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("prime-rib", "Prime Rib", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("short-rib", "Short Rib", "Carnes", "kg", "kg", True, 0.10, None, None),
    ("file-mignon", "Filé Mignon", "Carnes", "kg", "kg", True, 0.10, None, None),

    ("agua", "Água", "Bebidas", "litro", "garrafa", False, None, 1.5, "litro"),
    ("refrigerante", "Refrigerante", "Bebidas", "litro", "garrafa", False, None, 2.0, "litro"),
    ("suco", "Suco", "Bebidas", "litro", "caixa", False, None, 1.0, "litro"),
    ("cerveja", "Cerveja", "Bebidas", "litro", "lata", False, None, 0.35, "litro"),
    ("gelo", "Gelo", "Bebidas", "kg", "saco", False, None, 5.0, "kg"),

    ("carvao", "Carvão", "Extras", "kg", "saco", False, None, 3.0, "kg"),
    ("sal-grosso", "Sal grosso", "Extras", "kg", "pacote", False, None, 1.0, "kg"),
    ("acendedor", "Acendedor", "Extras", "unidade", "unidade", False, None, 1.0, "unidade"),
    ("fosforo-isqueiro", "Fósforo / isqueiro", "Extras", "unidade", "unidade", False, None, 1.0, "unidade"),
    ("copos", "Copos", "Extras", "unidade", "pacote", False, None, 50.0, "unidade"),
    ("pratos", "Pratos", "Extras", "unidade", "pacote", False, None, 10.0, "unidade"),
    ("talheres", "Talheres", "Extras", "unidade", "pacote", False, None, 20.0, "unidade"),
    ("guardanapos", "Guardanapos", "Extras", "unidade", "pacote", False, None, 50.0, "unidade"),
    ("sacos-lixo", "Sacos de lixo", "Extras", "unidade", "pacote", False, None, 10.0, "unidade"),
    ("papel-toalha", "Papel toalha", "Extras", "rolo", "pacote", False, None, 2.0, "rolo"),
    ("papel-aluminio", "Papel alumínio", "Extras", "rolo", "rolo", False, None, 1.0, "rolo"),
    ("palitos", "Palitos", "Extras", "unidade", "caixa", False, None, 100.0, "unidade"),

    ("pao-de-alho", "Pão de alho", "Acompanhamentos", "unidade", "pacote", False, None, 5.0, "unidade"),
    ("farofa", "Farofa", "Acompanhamentos", "kg", "pacote", False, None, 0.5, "kg"),
    ("vinagrete", "Vinagrete", "Acompanhamentos", "kg", "kg", True, 0.10, None, None),
    ("queijo-coalho", "Queijo coalho", "Acompanhamentos", "kg", "pacote", False, None, 0.5, "kg"),
    ("maionese", "Maionese", "Acompanhamentos", "kg", "pote", False, None, 0.5, "kg"),
    ("salada", "Salada", "Acompanhamentos", "kg", "kg", True, 0.10, None, None),
    ("arroz", "Arroz", "Acompanhamentos", "kg", "pacote", False, None, 1.0, "kg"),
    ("molhos", "Molhos", "Acompanhamentos", "litro", "frasco", False, None, 0.25, "litro"),
    ("pao", "Pão", "Acompanhamentos", "kg", "kg", True, 0.10, None, None),
]


def upgrade() -> None:
    bind = op.get_bind()

    categorias_ids: dict[str, int] = {}
    for nome, tipo in CATEGORIAS:
        categoria_id = bind.execute(
            sa.text("SELECT id FROM categorias WHERE nome = :nome"),
            {"nome": nome},
        ).scalar()

        if categoria_id is None:
            bind.execute(
                sa.text("INSERT INTO categorias (nome, tipo) VALUES (:nome, :tipo)"),
                {"nome": nome, "tipo": tipo},
            )
            categoria_id = bind.execute(
                sa.text("SELECT id FROM categorias WHERE nome = :nome"),
                {"nome": nome},
            ).scalar_one()
        else:
            bind.execute(
                sa.text("UPDATE categorias SET tipo = :tipo WHERE id = :id"),
                {"tipo": tipo, "id": categoria_id},
            )

        categorias_ids[nome] = int(categoria_id)

    for (
        slug, nome, categoria, unidade_consumo, unidade_venda,
        venda_fracionada, incremento_venda, quantidade_embalagem,
        unidade_embalagem,
    ) in PRODUTOS:
        produto_id = bind.execute(
            sa.text("SELECT id FROM produtos WHERE slug = :slug"),
            {"slug": slug},
        ).scalar()

        valores = {
            "categoria_id": categorias_ids[categoria],
            "slug": slug,
            "nome": nome,
            "unidade_consumo": unidade_consumo,
            "unidade_venda": unidade_venda,
            "venda_fracionada": bool(venda_fracionada),
            "incremento_venda": incremento_venda,
            "quantidade_embalagem": quantidade_embalagem,
            "unidade_embalagem": unidade_embalagem,
        }

        if produto_id is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO produtos (
                        categoria_id, produto_pai_id, tipo_produto, slug, nome,
                        unidade_consumo, unidade_venda, venda_fracionada,
                        incremento_venda, quantidade_embalagem, unidade_embalagem,
                        ativo
                    ) VALUES (
                        :categoria_id, NULL, 'generico', :slug, :nome,
                        :unidade_consumo, :unidade_venda, :venda_fracionada,
                        :incremento_venda, :quantidade_embalagem,
                        :unidade_embalagem, 1
                    )
                    """
                ),
                valores,
            )
        else:
            valores["id"] = int(produto_id)
            bind.execute(
                sa.text(
                    """
                    UPDATE produtos SET
                        categoria_id = :categoria_id,
                        tipo_produto = 'generico',
                        nome = :nome,
                        unidade_consumo = :unidade_consumo,
                        unidade_venda = :unidade_venda,
                        venda_fracionada = :venda_fracionada,
                        incremento_venda = :incremento_venda,
                        quantidade_embalagem = :quantidade_embalagem,
                        unidade_embalagem = :unidade_embalagem,
                        ativo = 1
                    WHERE id = :id
                    """
                ),
                valores,
            )


def downgrade() -> None:
    # Dados são preservados para não quebrar planejamentos, listas ou SKUs
    # comerciais que possam ter sido associados ao catálogo.
    pass
