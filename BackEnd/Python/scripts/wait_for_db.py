"""Aguarda o banco responder antes de migrations/startup em containers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time
from sqlalchemy import text
from database.connection import engine

ultimo = None
for tentativa in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Banco disponível.")
        raise SystemExit(0)
    except Exception as exc:
        ultimo = exc
        print(f"Aguardando banco ({tentativa + 1}/60)...")
        time.sleep(2)
raise SystemExit(f"Banco indisponível: {ultimo}")
