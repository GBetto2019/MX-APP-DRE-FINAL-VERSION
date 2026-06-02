"""MX Seguros — DRE-IA | Router: /metas"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_usuario
from app.models.schemas import MetasResponse
from app.services import dre_service

router = APIRouter(prefix="/metas", tags=["Metas"])


@router.get("", response_model=MetasResponse, summary="Metas e atingimento")
async def get_metas(
    request: Request,
    competencia: date = Query(..., description="Mês de referência (YYYY-MM-DD)"),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Retorna metas e percentual de atingimento para a competência.
    RLS filtra conforme perfil (§4.5):
    - Admin/Contador: todas as metas
    - Gestor: globais + equipe + produtores da equipe
    - Comercial: apenas meta individual própria
    """
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    return await dre_service.buscar_metas(competencia, usuario, db)
