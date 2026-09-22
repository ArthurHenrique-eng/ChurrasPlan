"""
Substitui a engine MySQL por SQLite em memoria ANTES de qualquer teste
importar `main` (que roda Base.metadata.create_all(bind=engine) assim que e
importado). Isso permite rodar toda a suite sem depender de um MySQL real -
a logica testada e exatamente a mesma que roda contra o banco de producao,
so a engine muda.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database.connection as conexao

conexao.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
conexao.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=conexao.engine)
