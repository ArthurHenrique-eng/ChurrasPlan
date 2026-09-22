from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from schemas.calculadora import (
    CalculoBebidasRequest,
    CalculoBebidasResponse,
    CalculoCarnesRequest,
    CalculoCarnesResponse,
    CalculoExtrasRequest,
    CalculoExtrasResponse,
    CompraCalculada,
    ItemCarneResponse,
)
from services import calculo_bebidas, calculo_carne, calculo_extras

router = APIRouter(prefix="/api/calculadora", tags=["calculadora"])


@router.post("/carnes", response_model=CalculoCarnesResponse)
def calcular_carnes(payload: CalculoCarnesRequest, db: Session = Depends(get_db)):
    try:
        perfil = payload.perfil_personalizado.to_dict() if payload.perfil_personalizado else None
        total_kg = payload.total_kg_manual
        if total_kg is None:
            total_kg = calculo_carne.calcular_quantidade_total_carne(
                payload.homens,
                payload.mulheres,
                payload.criancas,
                payload.duracao_horas,
                payload.perfil_consumo,
                perfil,
                payload.tipo_evento,
            )["total_kg"]
        itens = calculo_carne.distribuir_carnes(total_kg, [c.model_dump() for c in payload.carnes], db=db)
        carvao = calculo_carne.calcular_carvao(
            total_kg,
            payload.duracao_horas,
            carvao_ativo=payload.carvao_ativo,
            perfil_personalizado=perfil,
            perfil_consumo=payload.perfil_consumo,
            db=db,
        )
        return CalculoCarnesResponse(
            total_kg=total_kg,
            itens=[
                ItemCarneResponse(
                    nome=i["nome"], produto_slug=i["produto_slug"], percentual=i["percentual"],
                    quantidade_kg=i["quantidade_kg"], quantidade_compra_kg=i["quantidade_compra_kg"],
                    quantidade_embalagens=i["quantidade_embalagens"], unidade_venda=i["unidade_venda"],
                ) for i in itens
            ],
            carvao_necessario_kg=carvao["necessario_kg"],
            carvao_compra_kg=carvao["compra_kg"],
            carvao_sacos=carvao["sacos"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/bebidas", response_model=CalculoBebidasResponse)
def calcular_bebidas(payload: CalculoBebidasRequest, db: Session = Depends(get_db)):
    try:
        pessoas_total = payload.homens + payload.mulheres + payload.criancas
        perfil = payload.perfil_personalizado.to_dict() if payload.perfil_personalizado else None
        nao_alcoolicas = calculo_bebidas.calcular_bebidas_nao_alcoolicas(
            pessoas_total,
            payload.perfil_consumo,
            payload.bebidas_nao_alcoolicas_ativas,
            perfil,
            payload.tipo_evento,
        )
        compras_na = {}
        for slug, litros in nao_alcoolicas.items():
            produto, compra = calculo_bebidas.converter_bebida_para_compra(slug, litros, db)
            compras_na[slug] = CompraCalculada(
                necessario=compra.necessario,
                unidade_necessaria=compra.unidade_consumo,
                compra=compra.compra,
                unidade_compra=compra.unidade_compra,
                quantidade_embalagens=compra.embalagens,
                unidade_venda=produto.unidade_venda,
                tamanho_embalagem=compra.tamanho_embalagem,
                unidade_embalagem=compra.unidade_embalagem,
            )

        alcool_litros = 0.0
        alcool_unidades = 0
        alcool_unidade_venda = "lata"
        if payload.bebida_alcoolica_ativa:
            adultos_bebem = payload.homens_bebem_alcool + payload.mulheres_bebem_alcool
            alcool_litros = calculo_bebidas.calcular_bebida_alcoolica(
                adultos_bebem,
                payload.duracao_horas,
                payload.perfil_consumo,
                perfil,
                payload.tipo_evento,
            )["litros_total"]
            produto_alcool, compra_alcool = calculo_bebidas.converter_bebida_para_compra("cerveja", alcool_litros, db)
            alcool_unidades = compra_alcool.embalagens or 0
            alcool_unidade_venda = produto_alcool.unidade_venda

        gelo_kg = calculo_bebidas.calcular_gelo(
            pessoas_total,
            payload.duracao_horas,
            payload.perfil_consumo,
            perfil,
            payload.gelo_ativo,
        )
        gelo_compra = 0.0
        gelo_sacos = 0
        if payload.gelo_ativo:
            _, compra_gelo = calculo_bebidas.converter_bebida_para_compra("gelo", gelo_kg, db)
            gelo_compra = compra_gelo.compra
            gelo_sacos = compra_gelo.embalagens or 0

        return CalculoBebidasResponse(
            nao_alcoolicas_litros=nao_alcoolicas,
            nao_alcoolicas_compra=compras_na,
            alcool_litros_total=alcool_litros,
            alcool_unidades_sugeridas=alcool_unidades,
            alcool_unidade_venda=alcool_unidade_venda,
            gelo_kg=gelo_kg,
            gelo_compra_kg=gelo_compra,
            gelo_sacos=gelo_sacos,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/extras", response_model=CalculoExtrasResponse)
def calcular_extras_endpoint(payload: CalculoExtrasRequest):
    try:
        return CalculoExtrasResponse(
            extras=calculo_extras.calcular_extras(payload.pessoas_total, payload.carne_total_kg, payload.extras_ativos),
            acompanhamentos=calculo_extras.calcular_acompanhamentos(payload.pessoas_total, payload.acompanhamentos_ativos),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
