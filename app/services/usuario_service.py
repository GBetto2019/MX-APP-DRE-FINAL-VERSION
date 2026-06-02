"""
MX Seguros — DRE-IA | Serviço de gerenciamento de usuários.

Criação requer admin client (Supabase Auth + tabela usuarios).
Atualização/listagem usa o client do usuário (RLS aplica filtros).
Gestor não pode criar/promover admin ou contador.
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException, status as http_status
from supabase import Client

from app.auth import UsuarioAtual
from app.models.schemas import UsuarioCreate, UsuarioItem, UsuarioUpdate

logger = logging.getLogger(__name__)

_ROLES_RESTRICTOS = ("admin", "contador")


def _checar_escalada_de_privilegio(solicitante: UsuarioAtual, role_alvo: str | None) -> None:
    """Gestor não pode criar nem promover usuários para admin ou contador."""
    if solicitante.role == "gestor" and role_alvo in _ROLES_RESTRICTOS:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Gestor não pode atribuir role 'admin' ou 'contador'.",
        )


async def listar_usuarios(db: Client) -> list[UsuarioItem]:
    resp = (
        db.table("usuarios")
        .select("id, nome, email, role, equipe_id, produtor_id, ativo, criado_em")
        .order("nome")
        .execute()
    )
    return [UsuarioItem(**r) for r in (resp.data or [])]


async def buscar_usuario(usuario_id: UUID, db: Client) -> UsuarioItem:
    resp = (
        db.table("usuarios")
        .select("id, nome, email, role, equipe_id, produtor_id, ativo, criado_em")
        .eq("id", str(usuario_id))
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    return UsuarioItem(**resp.data)


async def criar_usuario(
    payload: UsuarioCreate,
    solicitante: UsuarioAtual,
    db_admin: Client,
) -> UsuarioItem:
    _checar_escalada_de_privilegio(solicitante, payload.role)

    # 1. Cria no Supabase Auth
    try:
        auth_resp = db_admin.auth.admin.create_user({
            "email":         payload.email,
            "password":      payload.senha,
            "email_confirm": True,
        })
        user_id = auth_resp.user.id
    except Exception as exc:
        logger.error("Falha ao criar usuário no Auth: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Falha ao criar usuário no Auth: {exc}",
        )

    # 2. Insere perfil na tabela usuarios (com rollback em caso de falha)
    dados: dict = {
        "id":    user_id,
        "nome":  payload.nome,
        "email": payload.email,
        "role":  payload.role,
        "ativo": True,
    }
    if payload.equipe_id:
        dados["equipe_id"] = str(payload.equipe_id)
    if payload.produtor_id:
        dados["produtor_id"] = str(payload.produtor_id)

    try:
        resp = db_admin.table("usuarios").insert(dados).execute()
        return UsuarioItem(**resp.data[0])
    except Exception as exc:
        logger.error("Falha ao inserir perfil — revertendo Auth user %s: %s", user_id, exc)
        try:
            db_admin.auth.admin.delete_user(user_id)
        except Exception as rb_exc:
            logger.error("Falha no rollback do Auth user %s: %s", user_id, rb_exc)
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Falha ao criar perfil do usuário: {exc}",
        )


async def atualizar_usuario(
    usuario_id: UUID,
    payload: UsuarioUpdate,
    solicitante: UsuarioAtual,
    db: Client,
) -> UsuarioItem:
    _checar_escalada_de_privilegio(solicitante, payload.role)

    dados = {k: v for k, v in payload.model_dump().items() if k in payload.model_fields_set}
    if not dados:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nenhum campo informado para atualizar.",
        )

    # Converte UUIDs para string (PostgREST exige)
    for campo in ("equipe_id", "produtor_id"):
        if campo in dados and dados[campo] is not None:
            dados[campo] = str(dados[campo])

    resp = db.table("usuarios").update(dados).eq("id", str(usuario_id)).execute()
    if not resp.data:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    return UsuarioItem(**resp.data[0])


async def desativar_usuario(
    usuario_id: UUID,
    solicitante_id: str,
    db: Client,
    db_admin: Client,
) -> None:
    if str(usuario_id) == solicitante_id:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Admin não pode desativar a própria conta.",
        )

    resp = db.table("usuarios").update({"ativo": False}).eq("id", str(usuario_id)).execute()
    if not resp.data:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    # Bloqueia login no Supabase Auth (876600h ≈ 100 anos)
    try:
        db_admin.auth.admin.update_user_by_id(str(usuario_id), {"ban_duration": "876600h"})
    except Exception as exc:
        logger.warning("Perfil desativado no DB mas falha ao banir no Auth %s: %s", usuario_id, exc)
