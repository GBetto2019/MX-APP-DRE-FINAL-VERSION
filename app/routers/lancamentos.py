"""
MX Seguros — DRE-IA | Router: /lancamentos
CRUD de despesas e receitas (admin + contador).
Deleção restrita a admin.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin, get_supabase_usuario
from app.middleware.periodo import validar_periodo
from app.middleware.rate_limit import limiter
from app.models.schemas import (
    DespesaAprovacaoRejeicao, DespesaCreate, DespesaItem, DespesasResponse, DespesaUpdate,
    ReceitaItem, ReceitaOutraCreate, ReceitaOutraUpdate, ReceitasResponse,
)
from app.services import financeiro_service
from app.services.dre_service import registrar_auditoria

router = APIRouter(prefix="/lancamentos", tags=["Lançamentos"])

_ROLES_LEITURA   = ("admin", "contador", "gestor", "comercial")
_ROLES_ESCRITA   = ("admin", "contador", "gestor", "comercial")
_ROLES_APROVACAO = ("admin", "gestor")


def _exigir_leitura(usuario: UsuarioAtual) -> None:
    if usuario.role not in _ROLES_LEITURA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso não autorizado.",
        )


def _exigir_despesas_leitura(usuario: UsuarioAtual) -> None:
    if usuario.role not in ("admin", "gestor", "contador"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso às despesas restrito a Admin, Gestor e Contador.",
        )


def _exigir_admin_ou_gestor(usuario: UsuarioAtual) -> None:
    """Remoção de despesas restrita a Admin e Gestor."""
    if usuario.role not in ("admin", "gestor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admin e Gestor podem remover despesas.",
        )


def _exigir_aprovacao(usuario: UsuarioAtual) -> None:
    if usuario.role not in _ROLES_APROVACAO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas Admin e Gestor podem aprovar ou rejeitar despesas.",
        )


# ── DESPESAS ──────────────────────────────────────────────────

@router.get(
    "/despesas",
    response_model=DespesasResponse,
    summary="Lista despesas do período",
)
@limiter.limit("30/minute")
async def listar_despesas(
    request: Request,
    periodo: tuple[date, date] = Depends(validar_periodo),
    centro_custo:   str | None = Query(None),
    banco_id:       str | None = Query(None),
    status_filter:  str | None = Query(None, alias="status", description="Filtrar por status: pendente | aprovada | rejeitada"),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    inicio, fim = periodo
    _exigir_despesas_leitura(usuario)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    resultado = await financeiro_service.buscar_despesas(
        inicio, fim, usuario, db, centro_custo, banco_id, status_filter
    )
    await registrar_auditoria(
        usuario, "consulta_despesas",
        {"inicio": str(inicio), "fim": str(fim)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return resultado


@router.post(
    "/despesas",
    response_model=DespesaItem,
    status_code=status.HTTP_201_CREATED,
    summary="Criar despesa",
)
async def criar_despesa(
    request: Request,
    payload: DespesaCreate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    if usuario.role not in _ROLES_ESCRITA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para criar despesas.",
        )
    if not payload.tipo_lancamento_id and not payload.categoria:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe 'tipo_lancamento_id' ou 'categoria'.",
        )
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    item = await financeiro_service.criar_despesa(payload, usuario, db)
    await registrar_auditoria(
        usuario, "criar_despesa",
        {"descricao": payload.descricao, "valor": str(payload.valor)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return item


@router.patch(
    "/despesas/{despesa_id}",
    response_model=DespesaItem,
    summary="Editar despesa",
)
async def editar_despesa(
    request: Request,
    despesa_id: UUID,
    payload: DespesaUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_leitura(usuario)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    item = await financeiro_service.atualizar_despesa(despesa_id, payload, db)
    await registrar_auditoria(
        usuario, "editar_despesa",
        {"despesa_id": str(despesa_id)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return item


@router.delete(
    "/despesas/{despesa_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover despesa (soft-delete)",
)
async def deletar_despesa(
    request: Request,
    despesa_id: UUID,
    excluir_futuras: bool = Query(False, description="Excluir também parcelas futuras do mesmo grupo"),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_admin_ou_gestor(usuario)
    db_admin = get_supabase_admin()
    await financeiro_service.deletar_despesa(despesa_id, db_admin, excluir_futuras=excluir_futuras)
    await registrar_auditoria(
        usuario, "deletar_despesa",
        {"despesa_id": str(despesa_id), "excluir_futuras": excluir_futuras},
        request.client.host if request.client else None,
        db_admin,
    )


@router.patch(
    "/despesas/{despesa_id}/aprovar",
    response_model=DespesaItem,
    summary="Aprovar despesa (admin/gestor)",
)
async def aprovar_despesa(
    request: Request,
    despesa_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_aprovacao(usuario)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    item = await financeiro_service.aprovar_despesa(despesa_id, usuario, db)
    await registrar_auditoria(
        usuario, "aprovar_despesa",
        {"despesa_id": str(despesa_id)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return item


@router.patch(
    "/despesas/{despesa_id}/rejeitar",
    response_model=DespesaItem,
    summary="Rejeitar despesa com justificativa (admin/gestor)",
)
async def rejeitar_despesa(
    request: Request,
    despesa_id: UUID,
    payload: DespesaAprovacaoRejeicao,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_aprovacao(usuario)
    if not payload.motivo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Justificativa é obrigatória para rejeição.",
        )
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    item = await financeiro_service.rejeitar_despesa(despesa_id, payload.motivo, usuario, db)
    await registrar_auditoria(
        usuario, "rejeitar_despesa",
        {"despesa_id": str(despesa_id), "motivo": payload.motivo},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return item


# ── RECEITAS ──────────────────────────────────────────────────

@router.get(
    "/receitas",
    response_model=ReceitasResponse,
    summary="Lista receitas do período (comissões + manuais)",
)
@limiter.limit("30/minute")
async def listar_receitas(
    request: Request,
    periodo: tuple[date, date] = Depends(validar_periodo),
    centro_custo: str | None = Query(None),
    banco_id:     str | None = Query(None),
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    inicio, fim = periodo
    _exigir_leitura(usuario)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    resultado = await financeiro_service.buscar_receitas(
        inicio, fim, usuario, db, centro_custo, banco_id
    )
    await registrar_auditoria(
        usuario, "consulta_receitas",
        {"inicio": str(inicio), "fim": str(fim)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return resultado


@router.post(
    "/receitas",
    response_model=ReceitaItem,
    status_code=status.HTTP_201_CREATED,
    summary="Criar receita manual",
)
async def criar_receita(
    request: Request,
    payload: ReceitaOutraCreate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    if usuario.role not in _ROLES_ESCRITA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para criar receitas.",
        )
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    item = await financeiro_service.criar_receita_outra(payload, usuario, db)
    await registrar_auditoria(
        usuario, "criar_receita",
        {"descricao": payload.descricao, "valor": str(payload.valor)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return item


@router.patch(
    "/receitas/{receita_id}",
    response_model=ReceitaItem,
    summary="Editar receita manual",
)
async def editar_receita(
    request: Request,
    receita_id: UUID,
    payload: ReceitaOutraUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_leitura(usuario)
    token = request.headers.get("authorization", "").replace("Bearer ", "")
    db = get_supabase_usuario(token)
    item = await financeiro_service.atualizar_receita_outra(receita_id, payload, db)
    await registrar_auditoria(
        usuario, "editar_receita",
        {"receita_id": str(receita_id)},
        request.client.host if request.client else None,
        get_supabase_admin(),
    )
    return item


@router.delete(
    "/receitas/{receita_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover receita manual",
)
async def deletar_receita(
    request: Request,
    receita_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)] = None,
):
    _exigir_leitura(usuario)
    db_admin = get_supabase_admin()
    await financeiro_service.deletar_receita_outra(receita_id, db_admin)
    await registrar_auditoria(
        usuario, "deletar_receita",
        {"receita_id": str(receita_id)},
        request.client.host if request.client else None,
        db_admin,
    )
