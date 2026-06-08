"""MX Seguros — DRE-IA | Router: /metas"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin, get_supabase_usuario
from app.middleware.rate_limit import limiter
from app.models.schemas import MetasResponse
from app.services import dre_service

router = APIRouter(prefix="/metas", tags=["Metas"])


@router.get("", response_model=MetasResponse, summary="Metas e atingimento do mês")
@limiter.limit("30/minute")
async def get_metas(
    request: Request,
    competencia: date = Query(..., description="Mês de competência (YYYY-MM-DD)"),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Retorna metas e percentual de atingimento para o mês informado.
    Disponível para todos os perfis (RLS filtra por produtor para Comercial).
    Apenas GET — criação/edição de metas é restrita a Admin/Gestor via Supabase direto.
    """
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)

    resultado = await dre_service.buscar_metas(competencia, usuario, db)

    await dre_service.registrar_auditoria(
        usuario, "consulta_metas",
        {"competencia": str(competencia)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )

    return resultado
