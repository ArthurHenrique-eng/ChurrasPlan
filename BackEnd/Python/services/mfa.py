"""TOTP com proteção contra replay e recuperação de uso único."""
import hmac
import secrets
import time
from datetime import timedelta
import pyotp
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session
from config import settings
from models import CredencialMFA, RecuperacaoMFA, SessaoUsuario
from services.auth import agora, hash_token
from services.criptografia import decifrar


def exigir_mfa(db: Session, sessao: SessaoUsuario) -> None:
    credencial = db.get(CredencialMFA, sessao.usuario_id)
    requerido = (sessao.usuario.papel == "admin" and settings.MFA_REQUIRED_ADMIN) or bool(credencial and credencial.ativo)
    if requerido and (not credencial or not credencial.ativo or not sessao.mfa_verificado_em
                      or sessao.mfa_verificado_em < agora() - timedelta(hours=settings.MFA_SESSION_HOURS)):
        raise HTTPException(403, detail={"codigo": "MFA_NECESSARIO", "mensagem": "Confirme o segundo fator em Segurança da conta."})


def consumir_codigo(db: Session, credencial: CredencialMFA, codigo: str, *, recuperacao: bool = True) -> bool:
    # A atualização condicional torna a aceitação atômica até em duas sessões.
    if codigo.isdigit() and len(codigo) == 6:
        totp = pyotp.TOTP(decifrar(credencial.segredo_cifrado))
        passo = int(time.time()) // 30
        for candidato in (passo, passo - 1, passo + 1):
            if hmac.compare_digest(totp.at(candidato * 30), codigo):
                resultado = db.execute(update(CredencialMFA).where(
                    CredencialMFA.usuario_id == credencial.usuario_id,
                    CredencialMFA.ultimo_passo < candidato,
                ).values(ultimo_passo=candidato))
                return resultado.rowcount == 1
    if recuperacao:
        resultado = db.execute(update(RecuperacaoMFA).where(
            RecuperacaoMFA.usuario_id == credencial.usuario_id,
            RecuperacaoMFA.codigo_hash == hash_token(codigo.strip().upper()),
            RecuperacaoMFA.usado_em.is_(None),
        ).values(usado_em=agora()))
        return resultado.rowcount == 1
    return False


def gerar_recuperacao(db: Session, usuario_id: int) -> list[str]:
    db.query(RecuperacaoMFA).filter_by(usuario_id=usuario_id).delete()
    codigos = [secrets.token_hex(8).upper() for _ in range(10)]
    db.add_all([RecuperacaoMFA(usuario_id=usuario_id, codigo_hash=hash_token(c)) for c in codigos])
    return codigos
