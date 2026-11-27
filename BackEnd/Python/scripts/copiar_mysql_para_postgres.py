"""Copia os dados de um banco MySQL do ChurrasPlan para um PostgreSQL recém-migrado.

Uso único na troca da Aiven (MySQL) pelo Neon (PostgreSQL). As URLs vêm de
variáveis de ambiente, para não ficarem no histórico do shell nem nos logs:

    ORIGEM_DATABASE_URL=mysql://...?ssl-mode=REQUIRED \
    DESTINO_DATABASE_URL=postgresql://... \
    python scripts/copiar_mysql_para_postgres.py            # só confere e conta
    python scripts/copiar_mysql_para_postgres.py --executar # copia

Regras:
- o destino precisa estar no head do Alembic e sem dados de usuários. As linhas
  que as próprias migrations inserem (catálogo base) são substituídas pelas da
  origem, para os IDs ficarem iguais;
- a origem precisa estar no head ou em uma revisão posterior conhecida; colunas
  que só existem na origem são ignoradas;
- tudo roda numa única transação no destino: se algo falha, nada é gravado;
- o script imprime só nomes de tabelas e contagens, nunca o conteúdo das linhas.
"""
from __future__ import annotations

import argparse
import os
import ssl
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import create_engine, func, inspect, select, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from config import normalizar_database_url  # noqa: E402
from database.connection import Base, configurar_sessao_postgresql  # noqa: E402
import models  # noqa: E402,F401  (registra as tabelas no metadata)

# Revisões que podem existir na origem além do head deste código. A 0025 veio de
# um preview da PR do Neon Auth: só adiciona usuarios.neon_auth_user_id e torna
# senha_hash anulável, então os dados continuam compatíveis com o head.
REVISOES_ORIGEM_EXTRAS = {"20261127_0025"}
LOTE = 1000


def _origem_mysql(url: str):
    """Aceita a URL do console da Aiven (mysql://...?ssl-mode=REQUIRED) ou a do app.

    ssl-mode=REQUIRED do MySQL significa conexão cifrada sem validar o
    certificado (a Aiven assina com uma CA própria do projeto). Quem quiser
    validar passa ssl_ca=... na própria URL, que o PyMySQL já entende.
    """
    url = url.strip()
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    if not url.startswith("mysql+pymysql://"):
        raise ValueError("ORIGEM_DATABASE_URL deve ser mysql:// ou mysql+pymysql://")
    analisada = make_url(url)
    query = dict(analisada.query)
    modo = str(query.pop("ssl-mode", query.pop("ssl_mode", "REQUIRED"))).upper()
    # DATETIME do MySQL não tem fuso; fixar UTC na sessão só protege eventuais TIMESTAMP.
    args: dict = {"init_command": "SET time_zone = '+00:00'"}
    if modo != "DISABLED" and not any(chave.startswith("ssl") for chave in query):
        args["ssl"] = {"check_hostname": False, "verify_mode": ssl.CERT_NONE}
    return analisada.set(query=query), args


def _head_alembic() -> str:
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _revisao(conexao) -> str | None:
    return conexao.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _contagens(conexao, tabelas) -> dict[str, int]:
    return {t.name: int(conexao.execute(select(func.count()).select_from(t)).scalar_one()) for t in tabelas}


def _autorreferencias(tabela) -> list[str]:
    return [fk.parent.name for fk in tabela.foreign_keys if fk.column.table is tabela]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--executar", action="store_true", help="copia de fato; sem isso só confere e conta")
    args = parser.parse_args()

    try:
        origem_url, origem_args = _origem_mysql(os.environ.get("ORIGEM_DATABASE_URL", ""))
    except ValueError as erro:
        print(erro, file=sys.stderr)
        return 2
    destino_url = normalizar_database_url(os.environ.get("DESTINO_DATABASE_URL", ""))
    if not destino_url.startswith("postgresql+psycopg://"):
        print("DESTINO_DATABASE_URL deve ser PostgreSQL", file=sys.stderr)
        return 2

    origem = create_engine(origem_url, connect_args=origem_args)
    destino = create_engine(destino_url, connect_args={"connect_timeout": 10})
    configurar_sessao_postgresql(destino)

    tabelas = Base.metadata.sorted_tables
    head = _head_alembic()

    with origem.connect() as conexao_origem:
        revisao_origem = _revisao(conexao_origem)
        colunas_origem = {
            nome: {c["name"] for c in inspect(conexao_origem).get_columns(nome)}
            for nome in inspect(conexao_origem).get_table_names()
        }
        faltando = [t.name for t in tabelas if t.name not in colunas_origem]
        contagem_origem = _contagens(conexao_origem, [t for t in tabelas if t.name in colunas_origem])

    with destino.connect() as conexao_destino:
        revisao_destino = _revisao(conexao_destino)
        contagem_destino = _contagens(conexao_destino, tabelas)

    print(f"head do código: {head}")
    print(f"origem (MySQL): revisão {revisao_origem}, {sum(contagem_origem.values())} linhas")
    print(f"destino (PostgreSQL): revisão {revisao_destino}, {sum(contagem_destino.values())} linhas")
    print(f"{'tabela':32} {'origem':>8} {'destino':>8}")
    for t in tabelas:
        print(f"{t.name:32} {contagem_origem.get(t.name, '-'):>8} {contagem_destino[t.name]:>8}")

    problemas = []
    if revisao_origem != head and revisao_origem not in REVISOES_ORIGEM_EXTRAS:
        problemas.append(f"origem em revisão inesperada: {revisao_origem}")
    if revisao_destino != head:
        problemas.append(f"destino precisa estar no head ({head}); está em {revisao_destino}")
    if faltando:
        problemas.append(f"tabelas ausentes na origem: {', '.join(faltando)}")
    if contagem_destino.get("usuarios", 0) or contagem_destino.get("organizacoes", 0):
        problemas.append("o destino já tem usuários ou organizações; a cópia só roda num banco recém-migrado")
    for t in tabelas:
        extras = sorted(c.name for c in t.columns if t.name in colunas_origem and c.name not in colunas_origem[t.name])
        if extras:
            problemas.append(f"{t.name}: colunas ausentes na origem: {', '.join(extras)}")
    if problemas:
        for p in problemas:
            print(f"ERRO: {p}", file=sys.stderr)
        return 1

    if not args.executar:
        print("Conferência ok. Rode com --executar para copiar.")
        return 0

    with origem.connect() as conexao_origem, destino.begin() as conexao_destino:
        nomes = ", ".join(f'"{t.name}"' for t in tabelas)
        conexao_destino.execute(text(f"TRUNCATE {nomes} RESTART IDENTITY CASCADE"))

        for t in tabelas:
            autorref = _autorreferencias(t)
            pk = list(t.primary_key.columns)
            consulta = select(*t.columns).order_by(*pk)
            pendentes: list[dict] = []
            resultado = conexao_origem.execution_options(stream_results=True).execute(consulta)
            while True:
                linhas = resultado.mappings().fetchmany(LOTE)
                if not linhas:
                    break
                lote = [dict(linha) for linha in linhas]
                if autorref:
                    for linha in lote:
                        valores = {c: linha[c] for c in autorref if linha[c] is not None}
                        if valores:
                            pendentes.append({**{c.name: linha[c.name] for c in pk}, **valores})
                            for c in valores:
                                linha[c] = None
                conexao_destino.execute(t.insert(), lote)
            for item in pendentes:
                filtro = [c == item[c.name] for c in pk]
                conexao_destino.execute(t.update().where(*filtro).values({c: item[c] for c in autorref if c in item}))

        for t in tabelas:
            pk = list(t.primary_key.columns)
            if len(pk) == 1 and pk[0].autoincrement in (True, "auto") and pk[0].type.python_type is int:
                conexao_destino.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('\"{t.name}\"', '{pk[0].name}'), "
                        f"COALESCE((SELECT MAX(\"{pk[0].name}\") FROM \"{t.name}\"), 1), "
                        f"(SELECT MAX(\"{pk[0].name}\") FROM \"{t.name}\") IS NOT NULL) "
                        f"WHERE pg_get_serial_sequence('\"{t.name}\"', '{pk[0].name}') IS NOT NULL"
                    )
                )

        copiadas = _contagens(conexao_destino, tabelas)
        diferencas = [t.name for t in tabelas if copiadas[t.name] != contagem_origem[t.name]]
        if diferencas:
            raise RuntimeError(f"contagens diferentes depois da cópia: {', '.join(diferencas)}")

    print(f"Cópia concluída: {sum(copiadas.values())} linhas em {len(tabelas)} tabelas, contagens iguais à origem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
