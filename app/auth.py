"""
MX Seguros — DRE-IA | Autenticação via JWT do Supabase.

O perfil do usuário (role) NUNCA vem do body/query da requisição.
Vem exclusivamente do JWT validado aqui. Tentativas de forjar role
via input são rejeitadas automaticamente.
"""
from __future__ import annotations

import asyncio
import time as _time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import cfg

# Cache em memória: {user_id: (role, tenant_id|None, equipe_id|None, produtor_id|None, permissions, timestamp)}
# TTL de 60s — esses campos raramente mudam.
_role_cache: dict[str, tuple[str, str | None, str | None, str | None, dict, float]] = {}
_ROLE_TTL = 60.0

BEARER = HTTPBearer()

ROLES_VALIDOS = {"admin", "gestor", "comercial", "contador", "super_admin"}


class UsuarioAtual(BaseModel):
    """Contexto do usuário extraído do JWT — fonte de verdade para permissões."""
    user_id:     str
    email:       str
    role:        str
    tenant_id:   str | None = None   # Sprint 4: multi-tenant
    equipe_id:   str | None = None
    produtor_id: str | None = None
    permissions: dict = {}


async def obter_usuario_atual(
    credenciais: Annotated[HTTPAuthorizationCredentials, Depends(BEARER)],
) -> UsuarioAtual:
    """
    Dependency do FastAPI: valida o JWT via Supabase Auth.
    O perfil (role) e tenant_id NUNCA vêm do token — vêm da tabela usuarios.
    """
    from supabase import create_client
    token = credenciais.credentials

    try:
        admin = create_client(cfg.supabase_url, cfg.supabase_service_role_key)
        resp = admin.auth.get_user(token)
        user = resp.user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não autenticado.",
        )

    role, tenant_id, equipe_id, produtor_id, permissions = await _buscar_perfil_no_banco(user.id)

    return UsuarioAtual(
        user_id=user.id,
        email=user.email or "",
        role=role,
        tenant_id=tenant_id,
        equipe_id=equipe_id,
        produtor_id=produtor_id,
        permissions=permissions,
    )


async def _buscar_perfil_no_banco(user_id: str) -> tuple[str, str | None, str | None, str | None, dict]:
    """
    Busca role, tenant_id, equipe_id, produtor_id e permissions do usuário, com cache TTL=60s.
    Source of truth para permissões — nunca confia no JWT.
    Graceful: se coluna tenant_id não existir ainda (migration pendente), retorna None.
    """
    from app.permissions import resolver_permissions, get_default_permissions

    now = _time.monotonic()
    cached = _role_cache.get(user_id)
    if cached and now - cached[5] < _ROLE_TTL:
        return cached[0], cached[1], cached[2], cached[3], cached[4]

    from supabase import create_client
    admin = create_client(cfg.supabase_url, cfg.supabase_service_role_key)
    try:
        # Tenta buscar com tenant_id e permissions (migrations mais recentes)
        resp = admin.table("usuarios") \
            .select("role, tenant_id, equipe_id, produtor_id, permissions") \
            .eq("id", user_id) \
            .limit(1) \
            .execute()
        if resp.data:
            row = resp.data[0]
            role = row["role"]
            tenant_id = row.get("tenant_id")
            equipe_id = row.get("equipe_id")
            produtor_id = row.get("produtor_id")
            permissions = resolver_permissions(role, row.get("permissions"))
            _role_cache[user_id] = (role, tenant_id, equipe_id, produtor_id, permissions, now)
            return role, tenant_id, equipe_id, produtor_id, permissions
    except Exception as e:
        err = str(e)
        # Fallback: coluna tenant_id ou permissions pode não existir ainda (migration pendente)
        if "schema cache" in err or "tenant_id" in err or "permissions" in err:
            try:
                resp = admin.table("usuarios") \
                    .select("role, equipe_id, produtor_id") \
                    .eq("id", user_id) \
                    .limit(1) \
                    .execute()
                if resp.data:
                    row = resp.data[0]
                    role = row["role"]
                    equipe_id = row.get("equipe_id")
                    produtor_id = row.get("produtor_id")
                    permissions = get_default_permissions(role)
                    _role_cache[user_id] = (role, None, equipe_id, produtor_id, permissions, now)
                    return role, None, equipe_id, produtor_id, permissions
            except Exception:
                pass

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Usuário não encontrado no sistema.",
    )


# Manter compatibilidade com código existente
async def _buscar_role_no_banco(user_id: str) -> str:
    role, _, _, _, _ = await _buscar_perfil_no_banco(user_id)
    return role


# ── Shortcuts para roles específicos ─────────────────────────

def _exigir_roles(*roles: str):
    async def _dep(usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)]) -> UsuarioAtual:
        if usuario.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado. Perfil '{usuario.role}' não tem permissão.",
            )
        return usuario
    return _dep


ExigeAdmin         = Depends(_exigir_roles("admin"))
ExigeAdminContador = Depends(_exigir_roles("admin", "contador"))
ExigeTodos         = Depends(obter_usuario_atual)
