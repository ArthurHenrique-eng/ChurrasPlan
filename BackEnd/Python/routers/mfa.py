import pyotp
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from config import settings
from database.connection import get_db
from models import CredencialMFA, RecuperacaoMFA, Usuario
from services.auth import usuario_atual, usuario_atual_com_csrf, verificar_senha, _buscar_sessao, agora
from services.criptografia import cifrar
from services.mfa import consumir_codigo, gerar_recuperacao
from services.seguranca import registrar_auditoria, verificar_limite, registrar_evento

router = APIRouter(prefix="/api/auth/mfa", tags=["MFA"])


class SenhaMFA(BaseModel):
    senha: str = Field(min_length=1, max_length=1024)


class CodigoMFA(BaseModel):
    codigo: str = Field(min_length=6, max_length=32)


class RevogarMFA(SenhaMFA, CodigoMFA):
    pass


@router.get("/status")
def status_mfa(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db),
               cookie: str | None = Cookie(None, alias=settings.SESSION_COOKIE_NAME)):
    credencial = db.get(CredencialMFA, usuario.id)
    sessao = _buscar_sessao(db, cookie)
    return {"ativo": bool(credencial and credencial.ativo),
            "obrigatorio": usuario.papel == "admin" and settings.MFA_REQUIRED_ADMIN,
            "verificado_em": sessao.mfa_verificado_em,
            "codigos_restantes": db.query(RecuperacaoMFA).filter_by(usuario_id=usuario.id, usado_em=None).count()}


@router.post("/configurar")
def configurar(payload: SenhaMFA, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    if not verificar_senha(payload.senha, usuario.senha_hash):
        raise HTTPException(401, detail="Senha inválida.")
    credencial = db.query(CredencialMFA).filter_by(usuario_id=usuario.id).with_for_update().first()
    if credencial and credencial.ativo:
        raise HTTPException(409, detail="MFA já configurado. Revogue antes de cadastrar outro autenticador.")
    segredo = pyotp.random_base32()
    if not credencial:
        credencial = CredencialMFA(usuario_id=usuario.id)
        db.add(credencial)
    credencial.segredo_cifrado, credencial.ultimo_passo = cifrar(segredo), -1
    db.commit()
    return {"segredo": segredo, "uri": pyotp.TOTP(segredo).provisioning_uri(usuario.email, issuer_name="ChurrasPlan"),
            "mensagem": "Adicione ao autenticador e confirme um código. O MFA ainda não está ativo."}


def _confirmar(db: Session, request: Request, usuario: Usuario, codigo: str, *, ativar: bool = False):
    chave = verificar_limite(db, request, tipo="mfa", limite=5, adicional=str(usuario.id))
    credencial = db.query(CredencialMFA).filter_by(usuario_id=usuario.id).with_for_update().first()
    if not credencial or (not ativar and not credencial.ativo) or not consumir_codigo(db, credencial, codigo, recuperacao=not ativar):
        registrar_evento(db, tipo="mfa", chave_hash=chave, sucesso=False)
        db.commit()
        raise HTTPException(401, detail="Código inválido, expirado ou já utilizado.")
    registrar_evento(db, tipo="mfa", chave_hash=chave, sucesso=True)
    return credencial


@router.post("/ativar")
def ativar(payload: CodigoMFA, request: Request, usuario: Usuario = Depends(usuario_atual_com_csrf),
           db: Session = Depends(get_db), cookie: str | None = Cookie(None, alias=settings.SESSION_COOKIE_NAME)):
    credencial = db.get(CredencialMFA, usuario.id)
    if credencial and credencial.ativo:
        raise HTTPException(409, detail="MFA já ativo.")
    credencial = _confirmar(db, request, usuario, payload.codigo, ativar=True)
    credencial.ativo = True
    for sessao in usuario.sessoes:
        sessao.revogada = True
    atual = _buscar_sessao(db, cookie)
    # A sessão atual já foi validada pelo dependency; revogar as demais.
    from models import SessaoUsuario
    from services.auth import hash_token
    atual = db.query(SessaoUsuario).filter_by(token_hash=hash_token(cookie)).one()
    atual.revogada, atual.mfa_verificado_em = False, agora()
    codigos = gerar_recuperacao(db, usuario.id)
    registrar_auditoria(db, usuario, acao="mfa_ativado", entidade="usuarios", entidade_id=usuario.id)
    db.commit()
    return {"ativo": True, "codigos_recuperacao": codigos}


@router.post("/verificar")
def verificar(payload: CodigoMFA, request: Request, usuario: Usuario = Depends(usuario_atual_com_csrf),
              db: Session = Depends(get_db), cookie: str | None = Cookie(None, alias=settings.SESSION_COOKIE_NAME)):
    _confirmar(db, request, usuario, payload.codigo)
    _buscar_sessao(db, cookie).mfa_verificado_em = agora()
    db.commit()
    return {"verificado": True}


@router.post("/revogar")
def revogar(payload: RevogarMFA, request: Request, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    if usuario.papel == "admin" and settings.MFA_REQUIRED_ADMIN:
        raise HTTPException(409, detail="MFA é obrigatório para administradores. Cadastre um novo autenticador por recuperação assistida.")
    if not verificar_senha(payload.senha, usuario.senha_hash):
        raise HTTPException(401, detail="Senha inválida.")
    _confirmar(db, request, usuario, payload.codigo)
    db.query(RecuperacaoMFA).filter_by(usuario_id=usuario.id).delete()
    db.query(CredencialMFA).filter_by(usuario_id=usuario.id).delete()
    for sessao in usuario.sessoes:
        sessao.revogada = True
    registrar_auditoria(db, usuario, acao="mfa_revogado", entidade="usuarios", entidade_id=usuario.id)
    db.commit()
    return {"mensagem": "MFA revogado. Entre novamente."}


@router.post("/substituir")
def substituir(payload: RevogarMFA, request: Request, usuario: Usuario = Depends(usuario_atual_com_csrf),
               db: Session = Depends(get_db), cookie: str | None = Cookie(None, alias=settings.SESSION_COOKIE_NAME)):
    if not verificar_senha(payload.senha, usuario.senha_hash):
        raise HTTPException(401, detail="Senha inválida.")
    credencial = _confirmar(db, request, usuario, payload.codigo)
    segredo = pyotp.random_base32()
    credencial.segredo_cifrado, credencial.ativo, credencial.ultimo_passo = cifrar(segredo), False, -1
    atual = _buscar_sessao(db, cookie)
    for sessao in usuario.sessoes:
        if sessao.id != atual.id:
            sessao.revogada = True
    atual.mfa_verificado_em = None
    registrar_auditoria(db, usuario, acao="mfa_substituicao_iniciada", entidade="usuarios", entidade_id=usuario.id)
    db.commit()
    return {"segredo": segredo, "mensagem": "Adicione a nova chave ao autenticador e confirme um código para reativar a proteção."}
