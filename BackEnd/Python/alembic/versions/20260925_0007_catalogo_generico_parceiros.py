"""Amplia o catálogo genérico usado por parceiros.

Revision ID: 20260925_0007
Revises: 20260922_0006
"""

from alembic import op
import sqlalchemy as sa


revision = "20260925_0007"
down_revision = "20260922_0006"
branch_labels = None
depends_on = None


CATEGORIAS = [
    ("Carnes", "carne"),
    ("Bebidas", "bebida"),
    ("Mercearia e alimentos", "mercearia"),
    ("Laticínios e frios", "laticinios"),
    ("Padaria", "padaria"),
    ("Hortifruti", "hortifruti"),
    ("Congelados", "congelado"),
    ("Limpeza", "limpeza"),
    ("Higiene pessoal", "higiene"),
    ("Descartáveis e utilidades", "descartavel"),
]

# slug, nome, categoria, unidade_consumo, unidade_venda
PRODUTOS = [
    # Carnes
    ("carne-bovina", "Carne bovina", "Carnes", "kg", "kg"),
    ("carne-suina", "Carne suína", "Carnes", "kg", "kg"),
    ("frango-generico", "Frango", "Carnes", "kg", "kg"),
    ("linguica-generica", "Linguiça", "Carnes", "kg", "kg"),
    ("peixe", "Peixe", "Carnes", "kg", "kg"),

    # Bebidas
    ("agua-mineral-generica", "Água mineral", "Bebidas", "litro", "unidade"),
    ("refrigerante-generico", "Refrigerante", "Bebidas", "litro", "unidade"),
    ("suco-generico", "Suco", "Bebidas", "litro", "unidade"),
    ("cerveja-generica", "Cerveja", "Bebidas", "litro", "unidade"),
    ("energetico", "Energético", "Bebidas", "litro", "unidade"),
    ("isotonico", "Isotônico", "Bebidas", "litro", "unidade"),
    ("agua-coco", "Água de coco", "Bebidas", "litro", "unidade"),
    ("cha-pronto", "Chá pronto", "Bebidas", "litro", "unidade"),
    ("cafe", "Café", "Bebidas", "kg", "pacote"),

    # Mercearia
    ("feijao", "Feijão", "Mercearia e alimentos", "kg", "pacote"),
    ("macarrao", "Macarrão", "Mercearia e alimentos", "kg", "pacote"),
    ("acucar", "Açúcar", "Mercearia e alimentos", "kg", "pacote"),
    ("sal-refinado", "Sal", "Mercearia e alimentos", "kg", "pacote"),
    ("oleo-cozinha", "Óleo de cozinha", "Mercearia e alimentos", "litro", "garrafa"),
    ("azeite", "Azeite", "Mercearia e alimentos", "litro", "garrafa"),
    ("ketchup", "Ketchup", "Mercearia e alimentos", "kg", "unidade"),
    ("mostarda", "Mostarda", "Mercearia e alimentos", "kg", "unidade"),
    ("molho-churrasco", "Molho para churrasco", "Mercearia e alimentos", "litro", "unidade"),
    ("tempero", "Tempero", "Mercearia e alimentos", "kg", "unidade"),
    ("conserva", "Conserva", "Mercearia e alimentos", "kg", "unidade"),
    ("biscoito", "Biscoito", "Mercearia e alimentos", "kg", "pacote"),

    # Laticínios e frios
    ("leite", "Leite", "Laticínios e frios", "litro", "unidade"),
    ("queijo-generico", "Queijo", "Laticínios e frios", "kg", "unidade"),
    ("presunto", "Presunto", "Laticínios e frios", "kg", "unidade"),
    ("manteiga", "Manteiga", "Laticínios e frios", "kg", "unidade"),
    ("margarina", "Margarina", "Laticínios e frios", "kg", "unidade"),
    ("requeijao", "Requeijão", "Laticínios e frios", "kg", "unidade"),
    ("iogurte", "Iogurte", "Laticínios e frios", "litro", "unidade"),

    # Padaria
    ("pao-frances", "Pão francês", "Padaria", "kg", "kg"),
    ("pao-forma", "Pão de forma", "Padaria", "kg", "pacote"),
    ("torrada", "Torrada", "Padaria", "kg", "pacote"),
    ("bolo", "Bolo", "Padaria", "kg", "unidade"),

    # Hortifruti
    ("tomate", "Tomate", "Hortifruti", "kg", "kg"),
    ("cebola", "Cebola", "Hortifruti", "kg", "kg"),
    ("alho", "Alho", "Hortifruti", "kg", "kg"),
    ("limao", "Limão", "Hortifruti", "kg", "kg"),
    ("batata", "Batata", "Hortifruti", "kg", "kg"),
    ("cenoura", "Cenoura", "Hortifruti", "kg", "kg"),
    ("alface", "Alface", "Hortifruti", "unidade", "unidade"),
    ("frutas", "Frutas", "Hortifruti", "kg", "kg"),

    # Congelados
    ("batata-congelada", "Batata congelada", "Congelados", "kg", "pacote"),
    ("hamburguer-congelado", "Hambúrguer congelado", "Congelados", "kg", "pacote"),
    ("vegetais-congelados", "Vegetais congelados", "Congelados", "kg", "pacote"),
    ("sorvete", "Sorvete", "Congelados", "litro", "unidade"),

    # Limpeza
    ("detergente", "Detergente", "Limpeza", "litro", "unidade"),
    ("esponja", "Esponja", "Limpeza", "unidade", "unidade"),
    ("desinfetante", "Desinfetante", "Limpeza", "litro", "unidade"),
    ("agua-sanitaria", "Água sanitária", "Limpeza", "litro", "unidade"),
    ("sabao-po", "Sabão em pó", "Limpeza", "kg", "unidade"),
    ("sabao-liquido", "Sabão líquido", "Limpeza", "litro", "unidade"),
    ("limpador-multiuso", "Limpador multiuso", "Limpeza", "litro", "unidade"),

    # Higiene
    ("papel-higienico", "Papel higiênico", "Higiene pessoal", "unidade", "pacote"),
    ("sabonete", "Sabonete", "Higiene pessoal", "unidade", "unidade"),
    ("alcool-gel", "Álcool em gel", "Higiene pessoal", "litro", "unidade"),
    ("lenco-umedecido", "Lenço umedecido", "Higiene pessoal", "unidade", "pacote"),

    # Descartáveis e utilidades
    ("copo-descartavel", "Copo descartável", "Descartáveis e utilidades", "unidade", "pacote"),
    ("prato-descartavel", "Prato descartável", "Descartáveis e utilidades", "unidade", "pacote"),
    ("talher-descartavel", "Talher descartável", "Descartáveis e utilidades", "unidade", "pacote"),
    ("guardanapo-generico", "Guardanapo", "Descartáveis e utilidades", "unidade", "pacote"),
    ("papel-toalha-generico", "Papel toalha", "Descartáveis e utilidades", "unidade", "pacote"),
    ("papel-aluminio-generico", "Papel alumínio", "Descartáveis e utilidades", "unidade", "unidade"),
    ("saco-lixo-generico", "Saco de lixo", "Descartáveis e utilidades", "unidade", "pacote"),
    ("carvao-generico", "Carvão", "Descartáveis e utilidades", "kg", "saco"),
    ("acendedor-generico", "Acendedor", "Descartáveis e utilidades", "unidade", "unidade"),
    ("fosforo-isqueiro-generico", "Fósforo / isqueiro", "Descartáveis e utilidades", "unidade", "unidade"),
]


def upgrade() -> None:
    bind = op.get_bind()

    categorias_ids: dict[str, int] = {}
    for nome, tipo in CATEGORIAS:
        existente = bind.execute(
            sa.text("SELECT id FROM categorias WHERE nome = :nome"),
            {"nome": nome},
        ).scalar()
        if existente is None:
            bind.execute(
                sa.text("INSERT INTO categorias (nome, tipo) VALUES (:nome, :tipo)"),
                {"nome": nome, "tipo": tipo},
            )
            existente = bind.execute(
                sa.text("SELECT id FROM categorias WHERE nome = :nome"),
                {"nome": nome},
            ).scalar_one()
        categorias_ids[nome] = int(existente)

    for slug, nome, categoria, unidade_consumo, unidade_venda in PRODUTOS:
        existe = bind.execute(
            sa.text("SELECT id FROM produtos WHERE slug = :slug"),
            {"slug": slug},
        ).scalar()
        if existe is not None:
            continue

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
                    NULL, NULL, NULL, :ativo
                )
                """
            ),
            {
                "categoria_id": categorias_ids[categoria],
                "slug": slug,
                "nome": nome,
                "unidade_consumo": unidade_consumo,
                "unidade_venda": unidade_venda,
                "venda_fracionada": False,
                "ativo": True,
            },
        )


def downgrade() -> None:
    # Catálogo de referência é mantido para não quebrar SKUs comerciais que
    # possam ter sido associados a estes produtos genéricos.
    pass
