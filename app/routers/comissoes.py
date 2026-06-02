"""MX Seguros — DRE-IA | Router: /comissoes"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_usuario
from app.middleware.periodo import validar_periodo
from app.middleware.rate_limit import limiter
from app.models.schemas import ComissoesResponse
from app.services import dre_service

router = APIRouter(prefix="/comissoes", tags=["Comissões"])


@router.get("", response_model=ComissoesResponse, summary="Comissões do período")
@limiter.limit("30/minute")
async def get_comissoes(
    request: Request,
    periodo: tuple[date, date] = Depends(validar_periodo),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Lista comissões do período. RLS filtra automaticamente:
    - Admin/Contador: todas
    - Gestor: apenas da sua equipe
    - Comercial: apenas as próprias
    """
    inicio, fim = periodo
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)

    resultado = await dre_service.buscar_comissoes(inicio, fim, usuario, db)

    from app.database import get_supabase_admin
    await dre_service.registrar_auditoria(
        usuario, "consulta_comissoes",
        {"inicio": str(inicio), "fim": str(fim)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )

    return resultado
