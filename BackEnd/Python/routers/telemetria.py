"""Sinais técnicos mínimos; separados de analytics e auditoria de segurança."""
import logging
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router=APIRouter(prefix='/api/telemetria',tags=['telemetria técnica'])
logger=logging.getLogger('churrasplan.frontend')


class ErroFrontendIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    codigo: Literal['falha_api','timeout_api','erro_js','rejeicao_js']
    pagina: Literal['home','planejamento','resultado','conta','parceiro','outro']


@router.post('/frontend',status_code=204)
def erro_frontend(payload: ErroFrontendIn):
    logger.warning('frontend_erro',extra={'evento':'frontend_erro','rota':payload.pagina,'tipo_erro':payload.codigo})
