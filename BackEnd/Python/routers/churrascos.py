"""CRUD transacional do churrasco e histórico autenticado."""
from decimal import Decimal
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.connection import get_db
from models import Churrasco, ChurrascoBebida, ChurrascoCarne, ChurrascoExtra, ListaCompras, ListaComprasItem, Usuario
from schemas.churrasco import ClaimChurrascoIn, ChurrascoCreate, ChurrascoHistoricoOut, ChurrascoOut, DivisaoChurrascoIn, ItemResultado, RepetirChurrascoIn
from services import calculo_bebidas, calculo_carne, calculo_extras
from services.auth import usuario_atual, usuario_atual_com_csrf, usuario_opcional, usuario_opcional_com_csrf
from services.catalogo_produtos import ProdutoComercial, converter_produto, resolver_produto
from services.calculo_precos import obter_melhor_oferta_atual

router = APIRouter(prefix="/api/churrascos", tags=["churrascos"])

EXTRAS_MAP = {
    "sal_grosso_kg": "sal-grosso", "copos_unidades": "copos", "pratos_unidades": "pratos",
    "talheres_unidades": "talheres", "guardanapos_unidades": "guardanapos", "sacos_lixo_unidades": "sacos-lixo",
    "acendedor_unidades": "acendedor", "fosforo_isqueiro_unidades": "fosforo-isqueiro",
    "papel_toalha_rolos": "papel-toalha", "papel_aluminio_rolos": "papel-aluminio", "palitos_unidades": "palitos",
}
ACOMP_MAP = {
    "pao_de_alho_unidades": "pao-de-alho", "farofa_kg": "farofa", "vinagrete_kg": "vinagrete",
    "queijo_coalho_kg": "queijo-coalho", "maionese_kg": "maionese", "salada_kg": "salada",
    "arroz_kg": "arroz", "molhos_litros": "molhos", "pao_kg": "pao",
}


def _decimal(valor: float | None, casas="0.001"):
    if valor is None:
        return None
    return Decimal(str(valor)).quantize(Decimal(casas))


def _verificar_acesso(churrasco: Churrasco, usuario: Usuario | None):
    if churrasco.usuario_id is not None and (not usuario or (usuario.id != churrasco.usuario_id and usuario.papel != "admin")):
        raise HTTPException(status_code=403, detail="Este churrasco pertence a outra conta.")


def _financeiro(db: Session, produto: ProdutoComercial, compra):
    if produto.id is None:
        return None, None, None
    oferta = obter_melhor_oferta_atual(db, produto.id)
    if not oferta:
        return None, None, None
    quantidade_cobrada = compra.compra if produto.venda_fracionada else (compra.embalagens or 0)
    subtotal = round(float(oferta.preco) * float(quantidade_cobrada), 2)
    return oferta, float(oferta.preco), subtotal


def _criar_modelo_item(db: Session, model_cls, churrasco: Churrasco, produto: ProdutoComercial,
                        necessario: float, *, tipo: str | None = None, percentual: float | None = None):
    compra = converter_produto(produto, necessario)
    oferta, preco_unitario, subtotal = _financeiro(db, produto, compra)
    kwargs = dict(
        churrasco=churrasco, produto_id=produto.id, preco_id=oferta.preco_id if oferta else None,
        produto_slug=produto.slug, nome_item=produto.nome, quantidade_necessaria=_decimal(compra.necessario),
        unidade_necessaria=compra.unidade_consumo, quantidade_compra=_decimal(compra.compra),
        unidade_compra=compra.unidade_compra, quantidade_embalagens=compra.embalagens,
        tamanho_embalagem=_decimal(compra.tamanho_embalagem), unidade_embalagem=compra.unidade_embalagem,
        unidade_venda=produto.unidade_venda, preco_unitario=_decimal(preco_unitario, "0.01"),
        subtotal_estimado=_decimal(subtotal, "0.01"), estabelecimento_id=oferta.estabelecimento_id if oferta else None,
    )
    if tipo is not None: kwargs["tipo"] = tipo
    if percentual is not None: kwargs["percentual"] = _decimal(percentual, "0.01")
    model = model_cls(**kwargs)
    db.add(model)
    return model


def _pessoas_que_comem_carne(payload: ChurrascoCreate) -> tuple[int, int]:
    sem_carne = min(payload.total_pessoas, payload.vegetarianos + payload.veganos)
    adultos_sem_carne = min(payload.total_adultos, sem_carne)
    criancas_sem_carne = max(0, sem_carne - adultos_sem_carne)
    return max(0, payload.total_adultos - adultos_sem_carne), max(0, payload.criancas - criancas_sem_carne)


def _montar_itens_e_persistir(db: Session, churrasco: Churrasco, payload: ChurrascoCreate) -> None:
    pessoas_total = payload.total_pessoas
    perfil = payload.perfil_personalizado.to_dict() if payload.perfil_personalizado else None
    adultos_carne, criancas_carne = _pessoas_que_comem_carne(payload)

    calc_carne = calculo_carne.calcular_quantidade_total_carne(
        adultos_carne, 0, criancas_carne, payload.duracao_horas,
        payload.perfil_consumo, perfil, payload.tipo_evento,
    )
    churrasco.carne_total_kg = _decimal(calc_carne["total_kg"])
    churrasco.carvao_ativo = payload.carvao_ativo
    churrasco.gelo_ativo = payload.gelo_ativo

    carnes = calculo_carne.distribuir_carnes(calc_carne["total_kg"], [c.model_dump() for c in payload.carnes], db=db)
    for carne in carnes:
        _criar_modelo_item(db, ChurrascoCarne, churrasco, carne["produto"], carne["quantidade_kg"], percentual=carne["percentual"])

    carvao = calculo_carne.calcular_carvao(
        calc_carne["total_kg"], payload.duracao_horas, carvao_ativo=payload.carvao_ativo,
        perfil_personalizado=perfil, perfil_consumo=payload.perfil_consumo, db=db,
    )
    churrasco.carvao_necessario_kg = _decimal(carvao["necessario_kg"])
    churrasco.carvao_compra_kg = _decimal(carvao["compra_kg"])
    if payload.carvao_ativo and carvao["produto"]:
        _criar_modelo_item(db, ChurrascoExtra, churrasco, carvao["produto"], carvao["necessario_kg"], tipo="carvao")

    nao_alcoolicas = calculo_bebidas.calcular_bebidas_nao_alcoolicas(
        pessoas_total, payload.perfil_consumo, payload.bebidas_nao_alcoolicas_ativas, perfil, payload.tipo_evento,
    )
    for slug, litros in nao_alcoolicas.items():
        _criar_modelo_item(db, ChurrascoBebida, churrasco, resolver_produto(db, slug=slug, categoria="bebida"), litros)

    if payload.bebida_alcoolica_ativa:
        litros = calculo_bebidas.calcular_bebida_alcoolica(
            payload.total_adultos_bebem, payload.duracao_horas, payload.perfil_consumo, perfil, payload.tipo_evento
        )["litros_total"]
        if litros > 0:
            _criar_modelo_item(db, ChurrascoBebida, churrasco, resolver_produto(db, slug="cerveja", categoria="bebida"), litros)

    gelo_kg = calculo_bebidas.calcular_gelo(pessoas_total, payload.duracao_horas, payload.perfil_consumo, perfil, payload.gelo_ativo)
    if payload.gelo_ativo and gelo_kg > 0:
        _criar_modelo_item(db, ChurrascoBebida, churrasco, resolver_produto(db, slug="gelo", categoria="bebida"), gelo_kg)

    extras = calculo_extras.calcular_extras(pessoas_total, calc_carne["total_kg"], payload.extras_ativos)
    for chave, valor in extras.items():
        slug = EXTRAS_MAP.get(chave)
        if slug:
            _criar_modelo_item(db, ChurrascoExtra, churrasco, resolver_produto(db, slug=slug, categoria="extra"), valor, tipo="extra")

    acompanhamentos = calculo_extras.calcular_acompanhamentos(pessoas_total, payload.acompanhamentos_ativos)
    for chave, valor in acompanhamentos.items():
        slug = ACOMP_MAP.get(chave)
        if slug:
            _criar_modelo_item(db, ChurrascoExtra, churrasco, resolver_produto(db, slug=slug, categoria="acompanhamento"), valor, tipo="acompanhamento")
    db.flush()


def _item_out(model, categoria: str) -> ItemResultado:
    return ItemResultado(
        produto_id=model.produto_id, produto_slug=model.produto_slug,
        percentual=float(model.percentual) if hasattr(model, "percentual") and model.percentual is not None else None,
        nome=model.nome_item, categoria=categoria,
        quantidade_necessaria=float(model.quantidade_necessaria), unidade_necessaria=model.unidade_necessaria,
        quantidade_compra=float(model.quantidade_compra), unidade_compra=model.unidade_compra,
        quantidade_embalagens=model.quantidade_embalagens,
        tamanho_embalagem=float(model.tamanho_embalagem) if model.tamanho_embalagem is not None else None,
        unidade_embalagem=model.unidade_embalagem, unidade_venda=model.unidade_venda,
        preco_estimado=float(model.preco_unitario) if model.preco_unitario is not None else None,
        preco_fonte="melhor_oferta_atual" if model.preco_unitario is not None else None,
        estabelecimento_id=model.estabelecimento_id,
        estabelecimento_nome=model.estabelecimento.nome if model.estabelecimento else None,
        subtotal_estimado=float(model.subtotal_estimado) if model.subtotal_estimado is not None else None,
    )


def _itens_persistidos(churrasco: Churrasco) -> list[ItemResultado]:
    itens = [_item_out(c, "carne") for c in churrasco.carnes]
    itens.extend(_item_out(b, "bebida") for b in churrasco.bebidas)
    itens.extend(_item_out(e, e.tipo) for e in churrasco.itens_extra)
    return itens


def _criar_lista_compras(db: Session, churrasco: Churrasco, itens: list[ItemResultado]):
    lista = ListaCompras(churrasco=churrasco)
    db.add(lista); db.flush()
    for item in itens:
        db.add(ListaComprasItem(
            lista_compras_id=lista.id, produto_id=item.produto_id, descricao=item.nome,
            quantidade=_decimal(item.quantidade_compra), unidade=item.unidade_compra,
            quantidade_embalagens=item.quantidade_embalagens, unidade_venda=item.unidade_venda,
            categoria=item.categoria, preco_unitario=_decimal(item.preco_estimado, "0.01"),
            subtotal_estimado=_decimal(item.subtotal_estimado, "0.01"), comprado=False,
        ))


def _calcular_custos(itens: list[ItemResultado]) -> tuple[float | None, bool]:
    subtotais = [i.subtotal_estimado for i in itens if i.subtotal_estimado is not None]
    algum_sem_preco = any(i.subtotal_estimado is None for i in itens)
    return (round(sum(subtotais), 2), algum_sem_preco) if subtotais else (None, algum_sem_preco)


def _avisos_restricoes(churrasco: Churrasco) -> list[str]:
    avisos = []
    if churrasco.vegetarianos: avisos.append(f"{churrasco.vegetarianos} convidado(s) vegetariano(s): revise opções sem carne na lista.")
    if churrasco.veganos: avisos.append(f"{churrasco.veganos} convidado(s) vegano(s): revise opções sem ingredientes de origem animal.")
    if churrasco.sem_carne_bovina: avisos.append(f"{churrasco.sem_carne_bovina} convidado(s) não consomem carne bovina.")
    if churrasco.sem_carne_suina: avisos.append(f"{churrasco.sem_carne_suina} convidado(s) não consomem carne suína.")
    if churrasco.intolerantes_lactose: avisos.append(f"{churrasco.intolerantes_lactose} convidado(s) têm intolerância à lactose.")
    if churrasco.alergias: avisos.append("Há alergias informadas. Confira ingredientes e contaminação cruzada antes da compra.")
    return avisos


def _montar_out(churrasco: Churrasco, itens: list[ItemResultado]) -> ChurrascoOut:
    custo_total = float(churrasco.custo_total_estimado) if churrasco.custo_total_estimado is not None else None
    itens_com_preco = sum(1 for i in itens if i.subtotal_estimado is not None)
    itens_sem_preco = len(itens) - itens_com_preco
    estimativa_completa = bool(itens) and itens_sem_preco == 0
    # Mesmo quando a cesta ainda possui itens sem preço, o subtotal conhecido
    # continua sendo útil ao usuário. Nessa situação `custo_por_pessoa` representa
    # uma estimativa PARCIAL; `estimativa_precos_completa` deixa isso explícito.
    custo_pessoa = (
        float(churrasco.custo_por_pessoa)
        if churrasco.custo_por_pessoa is not None
        else None
    )

    custo_total_real = None
    custo_real_completo = False
    if churrasco.lista_compras and churrasco.lista_compras.itens:
        itens_lista = churrasco.lista_compras.itens
        custo_real_completo = all(i.comprado and i.valor_pago_total is not None for i in itens_lista)
        if custo_real_completo:
            custo_total_real = round(sum(float(i.valor_pago_total) for i in itens_lista), 2)

    orcamento = float(churrasco.orcamento_maximo) if churrasco.orcamento_maximo is not None else None
    diferenca = None
    orcamento_status = None
    if orcamento is not None:
        if custo_total is None:
            orcamento_status = "sem_estimativa"
        elif not estimativa_completa:
            # Não declaramos "dentro" nem "acima" com uma cesta incompleta.
            orcamento_status = "estimativa_parcial"
        else:
            diferenca = round(orcamento - custo_total, 2)
            orcamento_status = "dentro" if diferenca >= 0 else "acima"

    if custo_total is None:
        aviso = "Nenhuma oferta de preço atual está cadastrada para os itens deste churrasco."
    elif not estimativa_completa:
        aviso = (
            f"Estimativa parcial: {itens_com_preco} de {len(itens)} item(ns) têm preço atual; "
            f"{itens_sem_preco} item(ns) ainda não entraram no total."
        )
    else:
        aviso = None

    divisao = None
    base_divisao = None
    if churrasco.dividir_entre:
        if custo_real_completo and custo_total_real is not None:
            divisao = round(custo_total_real / churrasco.dividir_entre, 2)
            base_divisao = "real"
        elif custo_total is not None:
            divisao = round(custo_total / churrasco.dividir_entre, 2)
            base_divisao = "estimado" if estimativa_completa else "estimado_parcial"
        else:
            base_divisao = "indisponivel"

    return ChurrascoOut(
        id=churrasco.id, usuario_id=churrasco.usuario_id, nome=churrasco.nome, status=churrasco.status,
        data_evento=churrasco.data_evento, tipo_evento=churrasco.tipo_evento, duracao_horas=churrasco.duracao_horas,
        perfil_consumo=churrasco.perfil_consumo, perfil_personalizado=churrasco.perfil_personalizado, adultos=churrasco.total_adultos,
        adultos_bebem_alcool=churrasco.total_adultos_bebem, homens=churrasco.homens, mulheres=churrasco.mulheres,
        criancas=churrasco.criancas, total_pessoas=churrasco.total_pessoas,
        vegetarianos=churrasco.vegetarianos, veganos=churrasco.veganos,
        sem_carne_bovina=churrasco.sem_carne_bovina, sem_carne_suina=churrasco.sem_carne_suina,
        intolerantes_lactose=churrasco.intolerantes_lactose, alergias=churrasco.alergias,
        outras_restricoes=churrasco.outras_restricoes, orcamento_maximo=orcamento,
        orcamento_status=orcamento_status, orcamento_diferenca=diferenca, dividir_entre=churrasco.dividir_entre,
        valor_por_divisao=divisao, base_divisao=base_divisao, carne_total_kg=float(churrasco.carne_total_kg or 0),
        carvao_ativo=churrasco.carvao_ativo, gelo_ativo=churrasco.gelo_ativo,
        carvao_necessario_kg=float(churrasco.carvao_necessario_kg) if churrasco.carvao_necessario_kg is not None else None,
        carvao_compra_kg=float(churrasco.carvao_compra_kg or 0), itens=itens,
        custo_total_estimado=custo_total, custo_por_pessoa=custo_pessoa,
        estimativa_precos_completa=estimativa_completa, itens_com_preco=itens_com_preco, itens_sem_preco=itens_sem_preco,
        custo_total_real=custo_total_real, custo_real_completo=custo_real_completo, aviso_precos=aviso,
        avisos_restricoes=_avisos_restricoes(churrasco),
    )


def _limpar_itens(db: Session, churrasco: Churrasco):
    churrasco.carnes.clear(); churrasco.bebidas.clear(); churrasco.itens_extra.clear()
    if churrasco.lista_compras: churrasco.lista_compras = None
    db.flush()


def _aplicar_payload(churrasco: Churrasco, payload: ChurrascoCreate):
    churrasco.nome = payload.nome
    churrasco.chave_cliente = payload.chave_cliente or churrasco.chave_cliente
    churrasco.data_evento = payload.data_evento
    churrasco.tipo_evento = payload.tipo_evento
    churrasco.duracao_horas = payload.duracao_horas
    churrasco.perfil_consumo = payload.perfil_consumo
    churrasco.perfil_personalizado = payload.perfil_personalizado.to_dict() if payload.perfil_personalizado else None
    churrasco.adultos = payload.total_adultos
    churrasco.adultos_bebem_alcool = payload.total_adultos_bebem
    churrasco.homens = payload.homens; churrasco.mulheres = payload.mulheres; churrasco.criancas = payload.criancas
    churrasco.homens_bebem_alcool = payload.homens_bebem_alcool; churrasco.mulheres_bebem_alcool = payload.mulheres_bebem_alcool
    churrasco.vegetarianos = payload.vegetarianos; churrasco.veganos = payload.veganos
    churrasco.sem_carne_bovina = payload.sem_carne_bovina; churrasco.sem_carne_suina = payload.sem_carne_suina
    churrasco.intolerantes_lactose = payload.intolerantes_lactose
    churrasco.alergias = payload.alergias; churrasco.outras_restricoes = payload.outras_restricoes
    churrasco.orcamento_maximo = _decimal(payload.orcamento_maximo, "0.01")
    churrasco.dividir_entre = payload.dividir_entre


def _recalcular(db: Session, churrasco: Churrasco, payload: ChurrascoCreate) -> ChurrascoOut:
    _aplicar_payload(churrasco, payload)
    _montar_itens_e_persistir(db, churrasco, payload)
    itens = _itens_persistidos(churrasco)
    custo_total, algum_sem_preco = _calcular_custos(itens)
    churrasco.custo_total_estimado = _decimal(custo_total, "0.01")
    churrasco.custo_por_pessoa = _decimal(
        (custo_total / churrasco.total_pessoas) if custo_total is not None and churrasco.total_pessoas > 0 else None,
        "0.01",
    )
    _criar_lista_compras(db, churrasco, itens); db.flush()
    return _montar_out(churrasco, itens)


@router.get("/meus", response_model=list[ChurrascoHistoricoOut])
def meus_churrascos(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    registros = db.query(Churrasco).filter(Churrasco.usuario_id == usuario.id).order_by(Churrasco.criado_em.desc()).all()
    resposta = []
    for c in registros:
        itens = _itens_persistidos(c)
        estimativa_completa = bool(itens) and all(i.subtotal_estimado is not None for i in itens)
        resposta.append(ChurrascoHistoricoOut(
            id=c.id, nome=c.nome, data_evento=c.data_evento, tipo_evento=c.tipo_evento,
            total_pessoas=c.total_pessoas,
            custo_total_estimado=float(c.custo_total_estimado) if c.custo_total_estimado is not None else None,
            estimativa_precos_completa=estimativa_completa,
            status=c.status, criado_em=c.criado_em, atualizado_em=c.atualizado_em,
        ))
    return resposta


@router.post("/{churrasco_id}/repetir", response_model=ChurrascoOut, status_code=201)
def repetir_churrasco(churrasco_id: int, payload: RepetirChurrascoIn, usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db)):
    origem = db.get(Churrasco, churrasco_id)
    if not origem or origem.usuario_id != usuario.id:
        raise HTTPException(status_code=404, detail="Churrasco não encontrado no seu histórico.")
    carnes = [{"nome": c.nome_item, "produto_slug": c.produto_slug, "percentual": float(c.percentual)} for c in origem.carnes]
    bebidas_slugs = [b.produto_slug for b in origem.bebidas if b.produto_slug not in {"cerveja", "gelo"}]
    dados = {
        "nome": payload.nome if payload.nome is not None else f"{origem.nome or 'Churrasco'} — repetição",
        "chave_cliente": f"repeat-{secrets.token_hex(12)}", "data_evento": payload.data_evento,
        "tipo_evento": origem.tipo_evento, "duracao_horas": origem.duracao_horas, "perfil_consumo": origem.perfil_consumo,
        "perfil_personalizado": origem.perfil_personalizado, "adultos": payload.adultos if payload.adultos is not None else origem.total_adultos,
        "adultos_bebem_alcool": payload.adultos_bebem_alcool if payload.adultos_bebem_alcool is not None else origem.total_adultos_bebem,
        "criancas": payload.criancas if payload.criancas is not None else origem.criancas,
        "vegetarianos": origem.vegetarianos, "veganos": origem.veganos, "sem_carne_bovina": origem.sem_carne_bovina,
        "sem_carne_suina": origem.sem_carne_suina, "intolerantes_lactose": origem.intolerantes_lactose,
        "alergias": origem.alergias, "outras_restricoes": origem.outras_restricoes,
        "orcamento_maximo": float(origem.orcamento_maximo) if origem.orcamento_maximo is not None else None,
        "carnes": carnes, "carvao_ativo": origem.carvao_ativo, "bebidas_nao_alcoolicas_ativas": bebidas_slugs,
        "bebida_alcoolica_ativa": any(b.produto_slug == "cerveja" for b in origem.bebidas),
        "gelo_ativo": origem.gelo_ativo,
        "extras_ativos": [e.produto_slug for e in origem.itens_extra if e.tipo == "extra" and e.produto_slug != "carvao"],
        "acompanhamentos_ativos": [e.produto_slug for e in origem.itens_extra if e.tipo == "acompanhamento"],
    }
    novo_payload = ChurrascoCreate.model_validate(dados)
    novo = Churrasco(chave_cliente=novo_payload.chave_cliente, usuario_id=usuario.id)
    db.add(novo)
    resposta = _recalcular(db, novo, novo_payload); db.commit()
    return resposta


@router.post("/{churrasco_id}/vincular", response_model=ChurrascoOut)
def vincular_churrasco(
    churrasco_id: int, payload: ClaimChurrascoIn,
    usuario: Usuario = Depends(usuario_atual_com_csrf), db: Session = Depends(get_db),
):
    churrasco = db.get(Churrasco, churrasco_id)
    if not churrasco or churrasco.chave_cliente != payload.chave_cliente:
        raise HTTPException(status_code=404, detail="Planejamento não encontrado para esta chave.")
    if churrasco.usuario_id not in {None, usuario.id}:
        raise HTTPException(status_code=409, detail="Este planejamento já pertence a outra conta.")
    churrasco.usuario_id = usuario.id
    db.commit(); db.refresh(churrasco)
    return _montar_out(churrasco, _itens_persistidos(churrasco))


@router.patch("/{churrasco_id}/divisao", response_model=ChurrascoOut)
def atualizar_divisao(
    churrasco_id: int, payload: DivisaoChurrascoIn, db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_opcional_com_csrf),
):
    churrasco = db.get(Churrasco, churrasco_id)
    if not churrasco: raise HTTPException(status_code=404, detail="Churrasco não encontrado")
    _verificar_acesso(churrasco, usuario)
    if payload.dividir_entre is not None and payload.dividir_entre > churrasco.total_pessoas:
        raise HTTPException(status_code=422, detail="A divisão não pode superar o total de convidados.")
    churrasco.dividir_entre = payload.dividir_entre
    db.commit(); db.refresh(churrasco)
    return _montar_out(churrasco, _itens_persistidos(churrasco))


@router.post("", response_model=ChurrascoOut, status_code=201)
def criar_churrasco(payload: ChurrascoCreate, db: Session = Depends(get_db), usuario: Usuario | None = Depends(usuario_opcional_com_csrf)):
    try:
        churrasco = db.query(Churrasco).filter(Churrasco.chave_cliente == payload.chave_cliente).first() if payload.chave_cliente else None
        if churrasco:
            _verificar_acesso(churrasco, usuario)
            _limpar_itens(db, churrasco)
        else:
            churrasco = Churrasco(chave_cliente=payload.chave_cliente, usuario_id=usuario.id if usuario else None)
            db.add(churrasco)
        if usuario and churrasco.usuario_id is None: churrasco.usuario_id = usuario.id
        resposta = _recalcular(db, churrasco, payload); db.commit(); return resposta
    except IntegrityError:
        db.rollback()
        if not payload.chave_cliente: raise
        churrasco = db.query(Churrasco).filter(Churrasco.chave_cliente == payload.chave_cliente).first()
        if not churrasco: raise
        _verificar_acesso(churrasco, usuario)
        _limpar_itens(db, churrasco); resposta = _recalcular(db, churrasco, payload); db.commit(); return resposta
    except ValueError as exc:
        db.rollback(); raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{churrasco_id}", response_model=ChurrascoOut)
def obter_churrasco(churrasco_id: int, db: Session = Depends(get_db), usuario: Usuario | None = Depends(usuario_opcional)):
    churrasco = db.get(Churrasco, churrasco_id)
    if not churrasco: raise HTTPException(status_code=404, detail="Churrasco não encontrado")
    _verificar_acesso(churrasco, usuario)
    return _montar_out(churrasco, _itens_persistidos(churrasco))


@router.put("/{churrasco_id}", response_model=ChurrascoOut)
def atualizar_churrasco(churrasco_id: int, payload: ChurrascoCreate, db: Session = Depends(get_db), usuario: Usuario | None = Depends(usuario_opcional_com_csrf)):
    churrasco = db.get(Churrasco, churrasco_id)
    if not churrasco: raise HTTPException(status_code=404, detail="Churrasco não encontrado")
    _verificar_acesso(churrasco, usuario)
    try:
        _limpar_itens(db, churrasco); resposta = _recalcular(db, churrasco, payload); db.commit(); return resposta
    except ValueError as exc:
        db.rollback(); raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{churrasco_id}", status_code=204)
def excluir_churrasco(churrasco_id: int, db: Session = Depends(get_db), usuario: Usuario | None = Depends(usuario_opcional_com_csrf)):
    churrasco = db.get(Churrasco, churrasco_id)
    if not churrasco: raise HTTPException(status_code=404, detail="Churrasco não encontrado")
    _verificar_acesso(churrasco, usuario)
    db.delete(churrasco); db.commit()
