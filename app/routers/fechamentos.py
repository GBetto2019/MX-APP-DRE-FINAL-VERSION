"""
MX Seguros — DRE-IA | Router: /fechamentos
Fechamento mensal: cria snapshot do DRE e marca o período como encerrado.
Leitura/criação: Admin e Contador. Reabertura: Admin exclusivo.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin, get_supabase_usuario
from app.models.schemas import FechamentoCreate, FechamentoItem, FechamentosResponse, ReabrirFechamento
from app.services import fechamento_service
from app.services.dre_service import registrar_auditoria

router = APIRouter(prefix="/fechamentos", tags=["Fechamentos"])


def _exigir_fechamento(usuario: UsuarioAtual) -> None:
    if usuario.role not in ("admin", "gestor", "contador"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fechamentos disponíveis apenas para Admin, Gestor e Contador.",
        )


def _exigir_admin_ou_gestor(usuario: UsuarioAtual) -> None:
    if usuario.role not in ("admin", "gestor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admin ou Gestor podem reabrir fechamentos.",
        )


@router.get("", response_model=FechamentosResponse, summary="Listar fechamentos mensais")
async def listar_fechamentos(
    request: Request,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_fechamento(usuario)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    return await fechamento_service.listar_fechamentos(db)


@router.post(
    "",
    response_model=FechamentoItem,
    status_code=status.HTTP_201_CREATED,
    summary="Criar fechamento mensal",
)
async def criar_fechamento(
    request: Request,
    payload: FechamentoCreate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Gera snapshot completo do DRE para o mês de `competencia` e marca o período
    como fechado. Após o fechamento, o mês pode ser reaberto apenas por Admin.
    Só pode haver um fechamento ativo por mês.
    """
    _exigir_fechamento(usuario)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    db_admin = get_supabase_admin()

    item = await fechamento_service.criar_fechamento(payload.competencia, usuario, db, db_admin)
    await registrar_auditoria(
        usuario, "criar_fechamento",
        {"competencia": str(payload.competencia)},
        request.client.host if request.client else None,
        db_admin,
    )
    return item


@router.post(
    "/{fechamento_id}/reabrir",
    response_model=FechamentoItem,
    summary="Reabrir fechamento (admin)",
)
async def reabrir_fechamento(
    request: Request,
    fechamento_id: UUID,
    payload: ReabrirFechamento,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """
    Reabre um fechamento ativo. O registro histórico é mantido.
    Um novo fechamento pode ser criado para o mesmo mês após a reabertura.
    """
    _exigir_admin_ou_gestor(usuario)
    if not payload.motivo or not payload.motivo.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Motivo de reabertura é obrigatório.",
        )
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    db_admin = get_supabase_admin()

    item = await fechamento_service.reabrir_fechamento(fechamento_id, payload.motivo, usuario, db)
    await registrar_auditoria(
        usuario, "reabrir_fechamento",
        {"fechamento_id": str(fechamento_id), "motivo": payload.motivo},
        request.client.host if request.client else None,
        db_admin,
    )
    return item
