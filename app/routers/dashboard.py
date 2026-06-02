"""MX Seguros — DRE-IA | Router: GET /dashboard (resposta agregada)"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_usuario
from app.middleware.periodo import validar_periodo
from app.middleware.rate_limit import limiter
from app.models.schemas import DashboardResponse
from app.services import dashboard_service, dre_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse, summary="Dashboard agregado")
@limiter.limit("30/minute")
async def get_dashboard(
    request: Request,
    periodo: tuple[date, date] = Depends(validar_periodo),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Retorna DRE + metas + alertas em uma única chamada (asyncio.gather internamente).
    Substitui 2-3 chamadas sequenciais do frontend por 1 chamada paralela.

    Campos visíveis variam conforme o perfil (§4.5 do SDD).
    """
    inicio, fim = periodo
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)

    resultado = await dashboard_service.buscar_dashboard(inicio, fim, usuario, db)

    await dre_service.registrar_auditoria(
        usuario, "consulta_dashboard",
        {"inicio": str(inicio), "fim": str(fim), "latencia_ms": resultado.latencia_ms},
        request.client.host if request.client else None,
        __import__("app.database", fromlist=["get_supabase_admin"]).get_supabase_admin(),
    )

    return resultado
