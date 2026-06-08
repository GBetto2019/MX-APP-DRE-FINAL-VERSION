"""MX Seguros — DRE-IA | Router: /repasses"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin, get_supabase_usuario
from app.middleware.periodo import validar_periodo
from app.middleware.rate_limit import limiter
from app.models.schemas import RepassesResponse
from app.services import dre_service

router = APIRouter(prefix="/repasses", tags=["Repasses"])


@router.get("", response_model=RepassesResponse, summary="Repasses a produtores no período")
@limiter.limit("30/minute")
async def get_repasses(
    request: Request,
    periodo: tuple[date, date] = Depends(validar_periodo),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Lista repasses a produtores no período informado.
    RLS filtra por perfil — Comercial vê apenas os próprios.
    """
    inicio, fim = periodo
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)

    resultado = await dre_service.buscar_repasses(inicio, fim, usuario, db)

    await dre_service.registrar_auditoria(
        usuario, "consulta_repasses",
        {"inicio": str(inicio), "fim": str(fim)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )

    return resultado
