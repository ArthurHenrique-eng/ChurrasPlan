from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload

from config import settings
from database.connection import get_db
from models import (
    AssinaturaUsuario, Churrasco, ConsentimentoUsuario, Estabelecimento, Preco,
    Usuario,
)
from schemas.privacidade import ExclusaoContaIn, PreferenciaMarketingIn
from services.auth import limpar_cookies, usuario_atual, usuario_atual_com_csrf, verificar_senha

router = APIRouter(prefix="/api/privacidade", tags=["privacidade-lgpd"])


def _json(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime):
        return valor.isoformat()
    return valor


def _modelo_dict(obj, excluir: set[str] | None = None) -> dict:
    excluir = excluir or set()
    return {
        c.name: _json(getattr(obj, c.name))
        for c in obj.__table__.columns
        if c.name not in excluir
    }


@router.get("/documentos")
def documentos_vigentes():
    return {
        "termos_versao": settings.TERMS_VERSION,
        "privacidade_versao": settings.PRIVACY_VERSION,
        "termos_url": "/termos.html",
        "privacidade_url": "/privacidade.html",
        "cookies_url": "/cookies.html",
    }


@router.get("/meus-consentimentos")
def meus_consentimentos(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    registros = (
        db.query(ConsentimentoUsuario)
        .filter(ConsentimentoUsuario.usuario_id == usuario.id)
        .order_by(ConsentimentoUsuario.criado_em.desc())
        .all()
    )
    return [
        {"tipo": r.tipo, "versao": r.versao, "concedido": r.concedido, "origem": r.origem, "criado_em": r.criado_em}
        for r in registros
    ]


@router.put("/marketing")
def atualizar_marketing(
    payload: PreferenciaMarketingIn,
    usuario: Usuario = Depends(usuario_atual_com_csrf),
    db: Session = Depends(get_db),
):
    # Marketing é opcional e separado dos documentos necessários ao serviço.
    registro = (
        db.query(ConsentimentoUsuario)
        .filter(
            ConsentimentoUsuario.usuario_id == usuario.id,
            ConsentimentoUsuario.tipo == "marketing",
            ConsentimentoUsuario.versao == "v1",
        )
        .first()
    )
    if registro is None:
        registro = ConsentimentoUsuario(
            usuario_id=usuario.id, tipo="marketing", versao="v1",
            concedido=payload.concedido, origem="minha_conta",
        )
        db.add(registro)
    else:
        registro.concedido = payload.concedido
        registro.origem = "minha_conta"
    db.commit()
    return {"mensagem": "Preferência atualizada.", "concedido": payload.concedido}


@router.get("/exportar")
def exportar_meus_dados(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Exportação legível por máquina para exercício do direito de acesso/portabilidade."""
    churrascos = (
        db.query(Churrasco)
        .options(
            joinedload(Churrasco.carnes), joinedload(Churrasco.bebidas),
            joinedload(Churrasco.itens_extra), joinedload(Churrasco.lista_compras),
            joinedload(Churrasco.convite),
        )
        .filter(Churrasco.usuario_id == usuario.id)
        .all()
    )
    dados_churrascos = []
    for c in churrascos:
        item = _modelo_dict(c)
        item["carnes"] = [_modelo_dict(x) for x in c.carnes]
        item["bebidas"] = [_modelo_dict(x) for x in c.bebidas]
        item["extras"] = [_modelo_dict(x) for x in c.itens_extra]
        if c.lista_compras:
            item["lista_compras"] = _modelo_dict(c.lista_compras)
            item["lista_compras"]["itens"] = [_modelo_dict(x) for x in c.lista_compras.itens]
        if c.convite:
            item["convite"] = _modelo_dict(c.convite)
            item["convite"]["respostas"] = [_modelo_dict(r, {"chave_resposta"}) for r in c.convite.respostas]
        dados_churrascos.append(item)

    estabelecimentos = db.query(Estabelecimento).filter(Estabelecimento.usuario_responsavel_id == usuario.id).all()
    consentimentos = db.query(ConsentimentoUsuario).filter(ConsentimentoUsuario.usuario_id == usuario.id).all()
    assinatura = db.query(AssinaturaUsuario).filter(AssinaturaUsuario.usuario_id == usuario.id).all()

    return {
        "formato": "ChurrasPlan-LGPD-export-v1",
        "usuario": _modelo_dict(usuario, {"senha_hash"}),
        "consentimentos": [_modelo_dict(c) for c in consentimentos],
        "churrascos": dados_churrascos,
        "estabelecimentos_responsavel": [_modelo_dict(e) for e in estabelecimentos],
        "assinaturas": [_modelo_dict(a) for a in assinatura],
        "observacao": "Tokens de autenticação, hashes de senha e segredos de sessão não fazem parte da exportação.",
    }


@router.delete("/minha-conta")
def excluir_minha_conta(
    payload: ExclusaoContaIn,
    response: Response,
    usuario: Usuario = Depends(usuario_atual_com_csrf),
    db: Session = Depends(get_db),
):
    if payload.confirmacao.strip().upper() != "EXCLUIR":
        raise HTTPException(status_code=422, detail="Digite EXCLUIR para confirmar a exclusão definitiva.")
    if not verificar_senha(payload.senha, usuario.senha_hash):
        raise HTTPException(status_code=403, detail="Senha incorreta.")

    # Eventos privados pertencem ao usuário e são removidos. Registros de negócio
    # (estabelecimentos/ofertas) permanecem apenas de forma desvinculada da pessoa.
    for churrasco in list(usuario.churrascos):
        db.delete(churrasco)
    db.query(Estabelecimento).filter(Estabelecimento.usuario_responsavel_id == usuario.id).update(
        {Estabelecimento.usuario_responsavel_id: None}, synchronize_session=False
    )
    db.query(Preco).filter(Preco.criado_por_usuario_id == usuario.id).update(
        {Preco.criado_por_usuario_id: None}, synchronize_session=False
    )
    db.delete(usuario)
    limpar_cookies(response)
    db.commit()
    return {"mensagem": "Conta e dados pessoais associados foram excluídos."}
