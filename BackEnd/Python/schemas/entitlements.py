"""Somente administradores podem conceder planos B2B temporários sem pagamento."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ConcessaoPlanoAdminUpdate(BaseModel):
    plano: Literal["free", "pro", "business"]
    expira_em: datetime | None = None
