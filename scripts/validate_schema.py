"""Valida que sql/schema.sql representa o mesmo conjunto de tabelas/colunas do ORM.

Não substitui `alembic check`: o objetivo é impedir que o schema de referência
fique desatualizado em relação ao head usado pela aplicação.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "BackEnd" / "Python"
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(BACKEND))

import models  # noqa: E402,F401
from database.connection import Base  # noqa: E402

schema_path = BACKEND / "sql" / "schema.sql"
sql = schema_path.read_text(encoding="utf-8")
blocks = {
    name: body
    for name, body in re.findall(
        r"CREATE TABLE\s+([A-Za-z0-9_]+)\s*\((.*?)\)\s*ENGINE=InnoDB;",
        sql,
        flags=re.S | re.I,
    )
}

orm_tables = set(Base.metadata.tables)
sql_tables = set(blocks)
errors: list[str] = []
if orm_tables != sql_tables:
    errors.append(f"tabelas apenas no ORM: {sorted(orm_tables - sql_tables)}")
    errors.append(f"tabelas apenas no SQL: {sorted(sql_tables - orm_tables)}")

ignore = {"PRIMARY", "FOREIGN", "UNIQUE", "CONSTRAINT", "CHECK", "KEY"}
for name in sorted(orm_tables & sql_tables):
    parsed: set[str] = set()
    for raw in blocks[name].splitlines():
        line = raw.strip().rstrip(",")
        if not line:
            continue
        first = line.split(None, 1)[0].strip("`").upper()
        if first in ignore:
            continue
        match = re.match(r"`?([A-Za-z_][A-Za-z0-9_]*)`?\s+", line)
        if match:
            parsed.add(match.group(1))
    expected = {c.name for c in Base.metadata.tables[name].columns}
    if parsed != expected:
        errors.append(f"{name}: apenas ORM={sorted(expected-parsed)}; apenas SQL={sorted(parsed-expected)}")

if "ip_criado" in sql or "ip_criado" in {c.name for c in Base.metadata.tables["sessoes_usuario"].columns}:
    errors.append("ip_criado não deve existir no head v6.3")

if errors:
    print("FALHA schema.sql:")
    for error in errors:
        print(" -", error)
    raise SystemExit(1)

print(f"OK: schema.sql alinhado ao ORM ({len(orm_tables)} tabelas)")
