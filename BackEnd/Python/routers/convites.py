import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from config import settings
from database.connection import get_db
from models import Churrasco, ConviteChurrasco, RespostaConvite, Usuario
from schemas.churrasco import ChurrascoCreate, ChurrascoOut
from schemas.convite import ConviteOut, ConvitePublicoOut, RespostaConviteIn, RespostaConviteOut, ResumoConviteOut
from services.auth import usuario_atual, usuario_atual_com_csrf
from services.seguranca import registrar_evento, verificar_limite

router = APIRouter(prefix="/api/convites", tags=["convites"])


def _churrasco_do_usuario(db: Session, churrasco_id: int, usuario: Usuario) -> Churrasco:
    c = db.get(Churrasco, churrasco_id)
    if not c or (c.usuario_id != usuario.id and usuario.papel != "admin"):
        raise HTTPException(status_code=404, detail="Churrasco não encontrado na sua conta.")
    return c


def _hash_chave_resposta(chave: str) -> str:
    # A chave pública funciona como um pequeno bearer secret para reabrir a
    # própria resposta. Armazenamos apenas um hash truncado a 192 bits, que
    # cabe no schema legado VARCHAR(48) e evita expor o segredo em caso de
    # leitura indevida do banco.
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()[:48]


def _buscar_resposta_por_chave(db: Session, convite: ConviteChurrasco, chave: str) -> RespostaConvite | None:
    chave = chave.strip()
    digest = _hash_chave_resposta(chave)
    candidatos = [digest]
    # Compatibilidade com respostas gravadas antes da proteção por hash.
    if len(chave) <= 48:
        candidatos.append(chave)
    r = db.query(RespostaConvite).filter(
        RespostaConvite.convite_id == convite.id,
        RespostaConvite.chave_resposta.in_(candidatos),
    ).first()
    if r and r.chave_resposta != digest:
        r.chave_resposta = digest
        db.flush()
    return r


def _aplicar_payload_resposta(r: RespostaConvite, payload: RespostaConviteIn) -> None:
    r.nome = payload.nome.strip()
    r.resposta = payload.resposta
    r.tipo_convidado = payload.tipo_convidado
    r.consome_alcool = payload.consome_alcool
    r.vegetariano = payload.vegetariano
    r.vegano = payload.vegano
    r.sem_carne_bovina = payload.sem_carne_bovina
    r.sem_carne_suina = payload.sem_carne_suina
    r.intolerante_lactose = payload.intolerante_lactose
    r.alergias = payload.alergias
    r.outras_restricoes = payload.outras_restricoes


def _resposta_out(r: RespostaConvite, chave_publica: str | None = None) -> RespostaConviteOut:
    return RespostaConviteOut(
        id=r.id, chave_resposta=chave_publica, nome=r.nome, resposta=r.resposta,
        tipo_convidado=r.tipo_convidado, consome_alcool=r.consome_alcool,
        vegetariano=r.vegetariano, vegano=r.vegano, sem_carne_bovina=r.sem_carne_bovina,
        sem_carne_suina=r.sem_carne_suina, intolerante_lactose=r.intolerante_lactose,
        alergias=r.alergias, outras_restricoes=r.outras_restricoes,
    )


def _resumo(c: Churrasco) -> ResumoConviteOut:
    respostas = list(c.convite.respostas if c.convite else [])
    conf = [r for r in respostas if r.resposta == "confirmado"]
    return ResumoConviteOut(
        churrasco_id=c.id,
        confirmados=len(conf), talvez=sum(r.resposta == "talvez" for r in respostas),
        nao=sum(r.resposta == "nao" for r in respostas), total_respostas=len(respostas),
        adultos_confirmados=sum(r.tipo_convidado == "adulto" for r in conf),
        criancas_confirmadas=sum(r.tipo_convidado == "crianca" for r in conf),
        consumidores_alcool_confirmados=sum(r.tipo_convidado == "adulto" and r.consome_alcool for r in conf),
        vegetarianos_confirmados=sum(r.vegetariano for r in conf), veganos_confirmados=sum(r.vegano for r in conf),
        sem_carne_bovina_confirmados=sum(r.sem_carne_bovina for r in conf), sem_carne_suina_confirmados=sum(r.sem_carne_suina for r in conf),
        intolerantes_lactose_confirmados=sum(r.intolerante_lactose for r in conf),
        respostas=[_resposta_out(r) for r in respostas],
    )


@router.post("/churrasco/{churrasco_id}", response_model=ConviteOut, status_code=201)
def criar_ou_obter_convite(churrasco_id: int, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    c = _churrasco_do_usuario(db, churrasco_id, usuario)
    convite = c.convite
    if not convite:
        convite = ConviteChurrasco(churrasco_id=c.id, codigo=secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:12])
        db.add(convite); db.flush()
    convite.ativo = True
    db.commit()
    return ConviteOut(
        codigo=convite.codigo, url=f"{settings.PUBLIC_APP_URL}/convite.html?codigo={convite.codigo}",
        churrasco_id=c.id, nome_churrasco=c.nome, data_evento=c.data_evento, ativo=convite.ativo,
        total_respostas=len(convite.respostas),
    )


@router.get("/churrasco/{churrasco_id}/resumo", response_model=ResumoConviteOut)
def resumo_convite(churrasco_id: int, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    c = _churrasco_do_usuario(db, churrasco_id, usuario)
    return _resumo(c)


@router.post("/churrasco/{churrasco_id}/aplicar-confirmados", response_model=ChurrascoOut)
def aplicar_confirmados(churrasco_id: int, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    c = _churrasco_do_usuario(db, churrasco_id, usuario)
    resumo = _resumo(c)
    if resumo.confirmados <= 0:
        raise HTTPException(status_code=422, detail="Ainda não há convidados confirmados para aplicar.")
    carnes = [{"nome": x.nome_item, "produto_slug": x.produto_slug, "percentual": float(x.percentual)} for x in c.carnes]
    bebidas_slugs = [b.produto_slug for b in c.bebidas if b.produto_slug not in {"cerveja", "gelo"}]
    alergias = "; ".join(filter(None, [r.alergias for r in c.convite.respostas if r.resposta == "confirmado"])) or None
    outras = "; ".join(filter(None, [r.outras_restricoes for r in c.convite.respostas if r.resposta == "confirmado"])) or None
    payload = ChurrascoCreate.model_validate({
        "nome": c.nome, "chave_cliente": c.chave_cliente, "data_evento": c.data_evento,
        "tipo_evento": c.tipo_evento, "duracao_horas": c.duracao_horas, "perfil_consumo": c.perfil_consumo,
        "perfil_personalizado": c.perfil_personalizado, "adultos": resumo.adultos_confirmados,
        "adultos_bebem_alcool": resumo.consumidores_alcool_confirmados, "criancas": resumo.criancas_confirmadas,
        "vegetarianos": resumo.vegetarianos_confirmados, "veganos": resumo.veganos_confirmados,
        "sem_carne_bovina": resumo.sem_carne_bovina_confirmados, "sem_carne_suina": resumo.sem_carne_suina_confirmados,
        "intolerantes_lactose": resumo.intolerantes_lactose_confirmados, "alergias": alergias, "outras_restricoes": outras,
        "orcamento_maximo": float(c.orcamento_maximo) if c.orcamento_maximo is not None else None, "dividir_entre": c.dividir_entre,
        "carnes": carnes, "carvao_ativo": c.carvao_ativo, "bebidas_nao_alcoolicas_ativas": bebidas_slugs,
        "bebida_alcoolica_ativa": any(b.produto_slug == "cerveja" for b in c.bebidas), "gelo_ativo": c.gelo_ativo,
        "extras_ativos": [e.produto_slug for e in c.itens_extra if e.tipo == "extra" and e.produto_slug != "carvao"],
        "acompanhamentos_ativos": [e.produto_slug for e in c.itens_extra if e.tipo == "acompanhamento"],
    })
    from routers.churrascos import _limpar_itens, _recalcular
    _limpar_itens(db, c); out = _recalcular(db, c, payload); db.commit()
    return out


@router.get("/publico/{codigo}", response_model=ConvitePublicoOut)
def obter_convite_publico(codigo: str, db: Session = Depends(get_db)):
    convite = db.query(ConviteChurrasco).filter(ConviteChurrasco.codigo == codigo, ConviteChurrasco.ativo.is_(True)).first()
    if not convite or (convite.expira_em and convite.expira_em < datetime.now(UTC).replace(tzinfo=None)):
        raise HTTPException(status_code=404, detail="Convite inválido ou expirado.")
    c = convite.churrasco
    return ConvitePublicoOut(
        codigo=convite.codigo, nome_churrasco=c.nome, data_evento=c.data_evento,
        tipo_evento=c.tipo_evento, duracao_horas=c.duracao_horas,
        organizador=c.usuario.nome if c.usuario else None,
    )


def _convite_publico_ativo(db: Session, codigo: str) -> ConviteChurrasco:
    convite = db.query(ConviteChurrasco).filter(ConviteChurrasco.codigo == codigo, ConviteChurrasco.ativo.is_(True)).first()
    if not convite or (convite.expira_em and convite.expira_em < datetime.now(UTC).replace(tzinfo=None)):
        raise HTTPException(status_code=404, detail="Convite inválido ou expirado.")
    return convite


@router.get("/publico/{codigo}/resposta/{chave}", response_model=RespostaConviteOut)
def obter_resposta_publica(codigo: str, chave: str, db: Session = Depends(get_db)):
    convite = _convite_publico_ativo(db, codigo)
    r = _buscar_resposta_por_chave(db, convite, chave)
    if not r:
        raise HTTPException(status_code=404, detail="Resposta não encontrada.")
    db.commit()
    return _resposta_out(r, chave)


@router.post("/publico/{codigo}/responder", response_model=RespostaConviteOut, status_code=201)
def responder_convite(codigo: str, payload: RespostaConviteIn, response: Response, request: Request, db: Session = Depends(get_db)):
    chave_rate = verificar_limite(
        db, request, tipo="rsvp", limite=settings.RATE_LIMIT_PUBLIC_ATTEMPTS, adicional=codigo
    )
    convite = _convite_publico_ativo(db, codigo)
    chave_publica = (payload.chave_resposta or secrets.token_urlsafe(32)).strip()
    if len(chave_publica) < 16 or len(chave_publica) > 64:
        raise HTTPException(status_code=422, detail="Chave de resposta inválida.")

    r = _buscar_resposta_por_chave(db, convite, chave_publica)
    if r is None:
        digest = _hash_chave_resposta(chave_publica)
        conflito = db.query(RespostaConvite).filter(RespostaConvite.chave_resposta == digest).first()
        if conflito:
            raise HTTPException(status_code=409, detail="Chave de resposta já utilizada em outro convite.")
        r = RespostaConvite(convite_id=convite.id, chave_resposta=digest)
        db.add(r)
    else:
        # POST é um upsert idempotente quando a chave é reapresentada.
        response.status_code = 200

    _aplicar_payload_resposta(r, payload)
    registrar_evento(db, tipo="rsvp", chave_hash=chave_rate, sucesso=True)
    db.commit(); db.refresh(r)
    return _resposta_out(r, chave_publica)
