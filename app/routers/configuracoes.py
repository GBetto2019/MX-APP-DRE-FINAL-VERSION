"""
MX Seguros — DRE-IA | Router: /configuracoes
Gerenciamento de parâmetros do sistema.
Leitura: todos autenticados.
Escrita/edição: exclusivo Admin.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin, get_supabase_usuario
from app.models.schemas import (
    BancoCreate, BancoItem, BancoUpdate,
    CentroCustoCreate, CentroCustoItem, CentroCustoUpdate,
    TipoLancamentoCreate, TipoLancamentoItem, TipoLancamentoUpdate,
    UsuarioCreate, UsuarioItem, UsuarioUpdate,
)
from app.services import financeiro_service, usuario_service
from app.services.dre_service import registrar_auditoria

router = APIRouter(prefix="/configuracoes", tags=["Configurações"])


def _exigir_admin(usuario: UsuarioAtual) -> None:
    if usuario.role not in ("admin", "gestor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admin ou Gestor pode alterar configurações.",
        )


def _exigir_admin_ou_gestor(usuario: UsuarioAtual) -> None:
    if usuario.role not in ("admin", "gestor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admin ou Gestor pode gerenciar usuários.",
        )


# ── BANCOS ────────────────────────────────────────────────────

@router.get("/bancos", response_model=list[BancoItem], summary="Listar bancos")
async def listar_bancos(
    request: Request,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    return await financeiro_service.listar_bancos(db)


@router.post(
    "/bancos",
    response_model=BancoItem,
    status_code=status.HTTP_201_CREATED,
    summary="Criar banco (admin)",
)
async def criar_banco(
    request: Request,
    payload: BancoCreate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin(usuario)
    db = get_supabase_admin()
    item = await financeiro_service.criar_banco(payload, db)
    await registrar_auditoria(
        usuario, "criar_banco", {"nome": payload.nome},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return item


@router.put(
    "/bancos/{banco_id}",
    response_model=BancoItem,
    summary="Atualizar banco (admin)",
)
async def atualizar_banco(
    request: Request,
    banco_id: UUID,
    payload: BancoUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin(usuario)
    return await financeiro_service.atualizar_banco(banco_id, payload, get_supabase_admin())


# ── CENTROS DE CUSTO ──────────────────────────────────────────

@router.get(
    "/centros-custo",
    response_model=list[CentroCustoItem],
    summary="Listar centros de custo",
)
async def listar_centros(
    request: Request,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    return await financeiro_service.listar_centros_custo(db)


@router.post(
    "/centros-custo",
    response_model=CentroCustoItem,
    status_code=status.HTTP_201_CREATED,
    summary="Criar centro de custo (admin)",
)
async def criar_centro(
    request: Request,
    payload: CentroCustoCreate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin(usuario)
    db = get_supabase_admin()
    item = await financeiro_service.criar_centro_custo(payload, db)
    await registrar_auditoria(
        usuario, "criar_centro_custo", {"nome": payload.nome, "codigo": payload.codigo},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return item


@router.put(
    "/centros-custo/{centro_id}",
    response_model=CentroCustoItem,
    summary="Atualizar centro de custo (admin)",
)
async def atualizar_centro(
    request: Request,
    centro_id: UUID,
    payload: CentroCustoUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin(usuario)
    return await financeiro_service.atualizar_centro_custo(centro_id, payload, get_supabase_admin())


# ── TIPOS DE LANÇAMENTO ───────────────────────────────────────

@router.get(
    "/tipos",
    response_model=list[TipoLancamentoItem],
    summary="Listar tipos de lançamento",
)
async def listar_tipos(
    request: Request,
    natureza: str | None = Query(None, description="'despesa' ou 'receita'"),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    return await financeiro_service.listar_tipos_lancamento(db, natureza)


@router.post(
    "/tipos",
    response_model=TipoLancamentoItem,
    status_code=status.HTTP_201_CREATED,
    summary="Criar tipo de lançamento (admin)",
)
async def criar_tipo(
    request: Request,
    payload: TipoLancamentoCreate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin(usuario)
    if payload.natureza not in ("despesa", "receita"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'natureza' deve ser 'despesa' ou 'receita'.",
        )
    db = get_supabase_admin()
    item = await financeiro_service.criar_tipo_lancamento(payload, db)
    await registrar_auditoria(
        usuario, "criar_tipo_lancamento", {"nome": payload.nome},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return item


@router.put(
    "/tipos/{tipo_id}",
    response_model=TipoLancamentoItem,
    summary="Atualizar tipo de lançamento (admin)",
)
async def atualizar_tipo(
    request: Request,
    tipo_id: UUID,
    payload: TipoLancamentoUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin(usuario)
    return await financeiro_service.atualizar_tipo_lancamento(tipo_id, payload, get_supabase_admin())


@router.delete(
    "/tipos/{tipo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar tipo de lançamento (admin)",
)
async def desativar_tipo(
    request: Request,
    tipo_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin(usuario)
    await financeiro_service.desativar_tipo_lancamento(tipo_id, get_supabase_admin())
