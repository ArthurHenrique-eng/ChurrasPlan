"""Fixture estritamente de CI para simular uma instalação B2B anterior à 0009.

Executar somente no banco EFÊMERO de testes já migrado até 20260925_0008.
Nunca executar em produção.
"""
import sys
from pathlib import Path

from sqlalchemy import text

# Scripts chamados por caminho a partir de BackEnd/Python precisam incluir o
# diretório do aplicativo para importar o pacote database de forma explícita.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database.connection import engine


def main():
    with engine.begin() as conn:
        uid = conn.execute(text("""
            INSERT INTO usuarios (nome, email, senha_hash, papel)
            VALUES ('Parceiro legado CI', 'saas-legado-migracao@example.invalid',
                    'hash-ficticio-sem-login', 'parceiro')
        """)).lastrowid
        eid = conn.execute(text("""
            INSERT INTO estabelecimentos
              (usuario_responsavel_id, slug, nome, tipo, parceiro_verificado, ativo)
            VALUES (:uid, 'saas-loja-legada-ci', 'Mercado Legado CI', 'mercado', 1, 1)
        """), {"uid": uid}).lastrowid
        pid = conn.execute(text("""
            INSERT INTO produtos (
                categoria_id, produto_pai_id, tipo_produto, slug, nome,
                marca, unidade_consumo, unidade_venda, venda_fracionada,
                quantidade_embalagem, unidade_embalagem, ativo
            ) VALUES (
                (SELECT categoria_id FROM (SELECT categoria_id FROM produtos
                 WHERE slug = 'agua') AS base), NULL, 'comercial',
                'saas-produto-legado-ci', 'Água Legada 1L', 'Marca Legada',
                'litro', 'garrafa', 0, 1.0, 'litro', 1
            )
        """)).lastrowid
        conn.execute(text("""
            INSERT INTO precos (
                produto_id, estabelecimento_id, criado_por_usuario_id, preco,
                moeda, fonte, origem, estoque_status, disponivel
            ) VALUES (:pid, :eid, :uid, 3.79, 'BRL', 'ci-legado',
                      'manual_parceiro', 'disponivel', 1)
        """), {"pid": pid, "eid": eid, "uid": uid})

        # Outro SKU ofertado tanto por loja associada quanto por loja SEM
        # responsável: a migração não pode atribuir essa marca a um tenant.
        nao_associada = conn.execute(text("""
            INSERT INTO estabelecimentos (slug, nome, tipo, parceiro_verificado, ativo)
            VALUES ('saas-loja-sem-dono-ci', 'Loja sem responsável CI', 'mercado', 0, 1)
        """)).lastrowid
        compartilhado = conn.execute(text("""
            INSERT INTO produtos (
                categoria_id, tipo_produto, slug, nome, marca, unidade_consumo,
                unidade_venda, venda_fracionada, ativo
            ) VALUES (
                (SELECT categoria_id FROM (SELECT categoria_id FROM produtos WHERE slug='agua') AS base),
                'comercial', 'saas-sku-ambiguo-ci', 'SKU ambíguo CI',
                'Marca compartilhada', 'litro', 'garrafa', 0, 1
            )
        """)).lastrowid
        for loja_id in [eid, nao_associada]:
            conn.execute(text("""
                INSERT INTO precos (
                    produto_id, estabelecimento_id, preco, origem, moeda,
                    estoque_status, disponivel, fonte
                ) VALUES (
                    :pid, :eid, 5.19, 'ci-legado', 'BRL', 'disponivel', 1,
                    'ci-teste-ambiguidade'
                )
            """), {"pid": compartilhado, "eid": loja_id})


if __name__ == "__main__":
    main()
