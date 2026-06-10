"""MX Seguros — DRE-IA | Router: /dre"""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_usuario
from app.middleware.rate_limit import limiter
from app.models.schemas import DREResponse, DashboardResponse, ReceitaRamoResponse, ReceitaTipoResponse
from app.services import dre_service

router = APIRouter(prefix="/dre", tags=["DRE"])

_MAX_PERIODO_DIAS = 365


@router.get("", response_model=DREResponse, summary="DRE do período")
@limiter.limit("30/minute")
async def get_dre(
    request: Request,
    inicio: date = Query(..., description="Data início (YYYY-MM-DD)"),
    fim:    date = Query(..., description="Data fim (YYYY-MM-DD)"),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Retorna o DRE para o período informado.
    Os campos visíveis variam conforme o perfil do usuário (§4.5 do escopo).
    RLS no banco garante que os valores calculados já reflitam apenas
    os dados que o usuário tem permissão de ver.
    """
    if fim < inicio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'fim' deve ser igual ou posterior a 'inicio'",
        )
    if (fim - inicio).days > _MAX_PERIODO_DIAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Período máximo permitido: 12 meses (365 dias).",
        )

    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)

    resultado = await dre_service.buscar_dre(inicio, fim, usuario, db)

    # Auditoria
    from app.database import get_supabase_admin
    await dre_service.registrar_auditoria(
        usuario, "consulta_dre",
        {"inicio": str(inicio), "fim": str(fim)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )

    return resultado


@router.get("/impostos", summary="Soma de despesas de impostos no período")
async def get_impostos_manuais(
    request: Request,
    inicio: date = Query(...),
    fim:    date = Query(...),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """Retorna a soma das despesas cujo tipo de lançamento contém 'imposto'."""
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)

    resp = (
        db.table("despesas")
        .select("valor, tipos_lancamento(nome)")
        .gte("competencia", inicio.isoformat())
        .lte("competencia", fim.isoformat())
        .neq("status", "excluida")
        .neq("status", "rejeitada")
        .execute()
    )
    from decimal import Decimal
    total = Decimal(0)
    for row in (resp.data or []):
        nome_tipo = ((row.get("tipos_lancamento") or {}).get("nome") or "").lower()
        if "imposto" in nome_tipo or "imposto" in (row.get("categoria") or "").lower():
            total += Decimal(str(row.get("valor", 0)))

    return {"total": float(total)}


@router.get("/ramos", response_model=ReceitaRamoResponse, summary="Receita por ramo")
async def get_receita_por_ramo(
    request: Request,
    inicio: date = Query(...),
    fim:    date = Query(...),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Receita bruta detalhada por ramo de seguro no período.
    Disponível para Admin e Gestor (§4.5).
    """
    if usuario.role not in ("admin", "gestor", "contador"):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Receita por ramo disponível apenas para Admin, Gestor e Contador.",
        )

    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    return await dre_service.buscar_receita_por_ramo(inicio, fim, db, usuario.user_id)


@router.get("/tipos", response_model=ReceitaTipoResponse, summary="Receita por tipo de lançamento")
async def get_receita_por_tipo(
    request: Request,
    inicio: date = Query(...),
    fim:    date = Query(...),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """Receita manual agrupada por tipo de lançamento no período."""
    if usuario.role not in ("admin", "gestor", "contador"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Receita por tipo disponível apenas para Admin, Gestor e Contador.",
        )
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    return await dre_service.buscar_receita_por_tipo(inicio, fim, db)
