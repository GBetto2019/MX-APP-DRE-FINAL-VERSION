"""MX Seguros — DRE-IA | Router: /metas"""
from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin, get_supabase_usuario
from app.models.schemas import MetaCadastroItem, MetaCreate, MetaUpdate, MetasResponse
from app.services import dre_service

router = APIRouter(prefix="/metas", tags=["Metas"])


def _exigir_admin_ou_gestor(usuario: UsuarioAtual) -> None:
    if usuario.role not in ("admin", "gestor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admin ou Gestor pode gerenciar metas.",
        )


@router.get(
    "/cadastro",
    response_model=list[MetaCadastroItem],
    summary="Listar metas cadastradas (admin)",
)
async def listar_metas_cadastro(
    request: Request,
    competencia: date = Query(..., description="Primeiro dia do mês (YYYY-MM-DD)"),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    """Lista todas as metas da competência para gestão (sem cálculo de atingimento)."""
    _exigir_admin_ou_gestor(usuario)
    db = get_supabase_admin()
    return await dre_service.listar_metas_cadastro(competencia, db)


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


@router.post(
    "",
    response_model=MetaCadastroItem,
    status_code=status.HTTP_201_CREATED,
    summary="Criar meta (admin)",
)
async def criar_meta(
    request: Request,
    payload: MetaCreate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin_ou_gestor(usuario)
    db = get_supabase_admin()
    item = await dre_service.criar_meta(payload, db)
    await dre_service.registrar_auditoria(
        usuario, "criar_meta",
        {
            "metrica": payload.metrica,
            "escopo": payload.escopo,
            "escopo_id": str(payload.escopo_id) if payload.escopo_id else None,
            "competencia": payload.competencia.isoformat(),
            "valor_alvo": str(payload.valor_alvo),
        },
        request.client.host if request.client else None,
        db,
    )
    return item


@router.put(
    "/{meta_id}",
    response_model=MetaCadastroItem,
    summary="Atualizar meta (admin)",
)
async def atualizar_meta(
    request: Request,
    meta_id: UUID,
    payload: MetaUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin_ou_gestor(usuario)
    db = get_supabase_admin()
    return await dre_service.atualizar_meta(meta_id, payload, db)


@router.delete(
    "/{meta_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir meta (admin)",
)
async def deletar_meta(
    request: Request,
    meta_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin_ou_gestor(usuario)
    db = get_supabase_admin()
    await dre_service.deletar_meta(meta_id, db)
