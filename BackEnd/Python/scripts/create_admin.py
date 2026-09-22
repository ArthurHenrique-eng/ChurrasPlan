"""Cria, promove ou redefine um administrador sem senha hardcoded.

Uso direto (Linux/macOS):
  ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='...' ADMIN_NAME='Admin' ADMIN_RESET_PASSWORD=true python scripts/create_admin.py

No Windows, prefira o helper da raiz:
  .\\scripts\\set_admin.ps1 -Email admin@example.com -Name "Administrador"
Ele solicita a senha sem gravá-la no histórico do PowerShell.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.connection import SessionLocal
from models import SessaoUsuario, Usuario
from services.auth import agora, hash_senha, normalizar_email


def preparar_admin(db, *, email: str, senha: str, nome: str, redefinir_senha: bool) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    novo = usuario is None

    if novo:
        usuario = Usuario(
            nome=nome,
            email=email,
            senha_hash=hash_senha(senha),
            papel="admin",
            ativo=True,
            email_verificado_em=agora(),
        )
        db.add(usuario)
        db.flush()
    else:
        usuario.papel = "admin"
        usuario.ativo = True
        usuario.email_verificado_em = usuario.email_verificado_em or agora()
        if nome and os.environ.get("ADMIN_UPDATE_NAME", "false").lower() in {"1", "true", "yes"}:
            usuario.nome = nome
        if redefinir_senha:
            usuario.senha_hash = hash_senha(senha)
            # Redefinir credencial administrativa invalida sessões existentes.
            db.query(SessaoUsuario).filter(
                SessaoUsuario.usuario_id == usuario.id,
                SessaoUsuario.revogada.is_(False),
            ).update({SessaoUsuario.revogada: True}, synchronize_session=False)

    db.commit()
    db.refresh(usuario)
    return usuario


def main() -> None:
    email = normalizar_email(os.environ.get("ADMIN_EMAIL", ""))
    senha = os.environ.get("ADMIN_PASSWORD", "")
    nome = (os.environ.get("ADMIN_NAME") or "Administrador").strip()
    redefinir = os.environ.get("ADMIN_RESET_PASSWORD", "false").lower() in {"1", "true", "yes"}

    if not email or not senha:
        raise SystemExit("Defina ADMIN_EMAIL e ADMIN_PASSWORD.")

    db = SessionLocal()
    try:
        usuario = preparar_admin(
            db,
            email=email,
            senha=senha,
            nome=nome,
            redefinir_senha=redefinir,
        )
        print(f"Administrador pronto: {usuario.email} (id={usuario.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
