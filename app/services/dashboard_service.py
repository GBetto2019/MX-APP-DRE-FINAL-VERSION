"""
MX Seguros — DRE-IA | Serviço de dashboard — agrega DRE + metas em uma única chamada.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date

from supabase import Client

from app.auth import UsuarioAtual
from app.logging_config import get_logger
from app.models.schemas import AlertaDashboard, DashboardResponse, DREResponse, MetasResponse
from app.services import dre_service

logger = get_logger(__name__)


def _gerar_alertas(dre_data: DREResponse, metas_data: MetasResponse | None) -> list[AlertaDashboard]:
    """Gera alertas baseados em limites de estorno e atingimento de metas."""
    alertas: list[AlertaDashboard] = []

    # Alerta de taxa de estorno alta (> 5% da receita bruta)
    receita = dre_data.dre.receita_bruta or 0
    estornos = dre_data.dre.estornos or 0
    if receita > 0:
        taxa_estorno = float(estornos / receita * 100)
        if taxa_estorno > 5:
            alertas.append(AlertaDashboard(
                tipo="estorno",
                mensagem=f"Taxa de estorno em {taxa_estorno:.1f}% — acima do limite de 5%",
                severidade="critico",
            ))

    # Alertas de metas abaixo do esperado (< 80% atingido)
    if metas_data and metas_data.items:
        for meta in metas_data.items:
            pct = meta.percentual_atingido
            if pct is not None and pct < 80:
                alertas.append(AlertaDashboard(
                    tipo="meta",
                    mensagem=f"Meta ({meta.escopo}) atingida em {pct:.0f}%",
                    severidade="aviso",
                ))

    return alertas


async def buscar_dashboard(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
) -> DashboardResponse:
    t0 = time.monotonic()

    competencia = date(inicio.year, inicio.month, 1)

    dre_data, metas_data = await asyncio.gather(
        dre_service.buscar_dre(inicio, fim, usuario, db),
        dre_service.buscar_metas(competencia, usuario, db),
    )

    alertas = _gerar_alertas(dre_data, metas_data)

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
        metas=metas_data.model_dump() if metas_data else None,
        alertas=alertas,
        latencia_ms=latencia_ms,
    )
