"""
Serviço de dashboard — agrega DRE + metas + alertas em uma única chamada.
Usa asyncio.gather() para buscar dados em paralelo, reduzindo latência.

Task 1.3 — Sprint 1 Performance.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date
from decimal import Decimal

from supabase import Client

from app.auth import UsuarioAtual
from app.logging_config import get_logger
from app.models.schemas import AlertaDashboard, DashboardResponse, MetasResponse
from app.services import dre_service

logger = get_logger(__name__)


async def buscar_dashboard(
    inicio: date,
    fim: date,
    usuario: UsuarioAtual,
    db: Client,
) -> DashboardResponse:
    """
    Agrega DRE + metas + estornos em paralelo via asyncio.gather.
    Gera alertas automáticos conforme as regras do SDD §5.1.
    """
    t0 = time.monotonic()

    # Competência para metas = primeiro mês do período
    competencia_metas = date(inicio.year, inicio.month, 1)

    # Buscar DRE e metas em paralelo — principal ganho de performance
    dre_task    = dre_service.buscar_dre(inicio, fim, usuario, db)
    metas_task  = dre_service.buscar_metas(competencia_metas, usuario, db)
    estorno_task = dre_service.buscar_estornos(inicio, fim, usuario, db)

    dre_data, metas_data, estorno_data = await asyncio.gather(
        dre_task, metas_task, estorno_task,
        return_exceptions=False,
    )

    alertas = _gerar_alertas(dre_data.dre, metas_data, estorno_data, usuario.role)

    latencia_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "dashboard_carregado",
        usuario_id=usuario.user_id,
        role=usuario.role,
        latencia_ms=latencia_ms,
        alertas=len(alertas),
    )

    return DashboardResponse(
        periodo=dre_data.periodo,
        dre=dre_data.dre,
        perfil=usuario.role,
        metas=metas_data,
        alertas=alertas,
        latencia_ms=latencia_ms,
    )


def _gerar_alertas(dre, metas, estornos, role: str) -> list[AlertaDashboard]:
    """Regras de alerta automático conforme SDD §5.1."""
    alertas: list[AlertaDashboard] = []

    # Alerta 1: taxa de estorno > 5%
    if role in ("admin", "gestor", "contador"):
        if estornos.alerta_5pct:
            taxa = estornos.taxa_estorno
            alertas.append(AlertaDashboard(
                tipo="estorno_alto",
                mensagem=(
                    f"Taxa de estorno em {float(taxa):.1f}% — acima do limite de 5%. "
                    "Verifique os cancelamentos do período."
                ),
                severidade="aviso",
            ))

    # Alerta 2: metas com < 80% atingido
    if metas and metas.items:
        from datetime import date as d
        hoje = d.today()
        fim_mes = date(hoje.year, hoje.month, 1)
        import calendar
        ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
        dias_restantes = ultimo_dia - hoje.day

        for meta in metas.items:
            pct = float(meta.percentual)
            if pct < 80 and dias_restantes <= 5:
                alertas.append(AlertaDashboard(
                    tipo="meta_atrasada",
                    mensagem=(
                        f"Meta de {meta.metrica} em {pct:.0f}% — "
                        f"faltam {dias_restantes} dias úteis para o fim do mês."
                    ),
                    severidade="aviso" if role == "admin" else "info",
                ))
                break  # um alerta de meta por vez

    return alertas
