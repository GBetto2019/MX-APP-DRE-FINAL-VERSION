"""MX Seguros — DRE-IA | Router: /usuarios"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin, get_supabase_usuario
from app.models.schemas import UsuarioCreate, UsuarioItem, UsuarioUpdate
from app.services import usuario_service
from app.services.dre_service import registrar_auditoria

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


def _exigir_admin_ou_gestor(usuario: UsuarioAtual) -> None:
    if usuario.role not in ("admin", "gestor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admin ou Gestor pode gerenciar usuários.",
        )


@router.get("/me", response_model=UsuarioItem, summary="Perfil do usuário autenticado")
async def meu_perfil(
    request: Request,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    return await usuario_service.buscar_usuario(UUID(usuario.user_id), db)


@router.get("", response_model=dict, summary="Listar usuários (admin/gestor)")
async def listar_usuarios(
    request: Request,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin_ou_gestor(usuario)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    items = await usuario_service.listar_usuarios(db)
    return {"total": len(items), "items": [i.model_dump() for i in items]}


@router.post(
    "",
    response_model=UsuarioItem,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário (admin/gestor)",
)
async def criar_usuario(
    request: Request,
    payload: UsuarioCreate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin_ou_gestor(usuario)
    db_admin = get_supabase_admin()
    novo = await usuario_service.criar_usuario(payload, usuario, db_admin)
    await registrar_auditoria(
        usuario, "criar_usuario",
        {"email": payload.email, "role": payload.role},
        request.client.host if request.client else None,
        db_admin,
    )
    return novo


@router.patch(
    "/{usuario_id}",
    response_model=UsuarioItem,
    summary="Atualizar usuário (admin/gestor)",
)
async def atualizar_usuario(
    request: Request,
    usuario_id: UUID,
    payload: UsuarioUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin_ou_gestor(usuario)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    atualizado = await usuario_service.atualizar_usuario(usuario_id, payload, usuario, db)
    await registrar_auditoria(
        usuario, "atualizar_usuario",
        {"usuario_id": str(usuario_id), **payload.model_dump(exclude_none=True)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return atualizado


@router.delete(
    "/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar usuário / soft-delete (admin)",
)
async def desativar_usuario(
    request: Request,
    usuario_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    if usuario.role not in ("admin", "gestor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas Admin ou Gestor pode desativar usuários.")
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    db_admin = get_supabase_admin()
    await usuario_service.desativar_usuario(usuario_id, usuario.user_id, db, db_admin)
    await registrar_auditoria(
        usuario, "desativar_usuario", {"usuario_id": str(usuario_id)},
        request.client.host if request.client else None,
        db_admin,
    )
