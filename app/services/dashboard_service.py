"""
Serviço de dashboard — agrega DRE em uma única chamada.
"""
from __future__ import annotations

import time
from datetime import date

from supabase import Client

from app.auth import UsuarioAtual
from app.logging_config import get_logger
from app.models.schemas import DashboardResponse
from app.services import dre_service

logger = get_logger(__name__)


async def buscar_dashboard(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
) -> DashboardResponse:
    t0 = time.monotonic()

    dre_data = await dre_service.buscar_dre(inicio, fim, usuario, db)

    latencia_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "dashboard_carregado",
        usuario_id=usuario.user_id,
        role=usuario.role,
        latencia_ms=latencia_ms,
    )

    return DashboardResponse(
        periodo=dre_data.periodo,
        dre=dre_data.dre,
        perfil=usuario.role,
        alertas=[],
        latencia_ms=latencia_ms,
    )
