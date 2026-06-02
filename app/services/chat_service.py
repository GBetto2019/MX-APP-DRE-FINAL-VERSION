"""Serviço de persistência do histórico de chat."""
from __future__ import annotations

import logging
from uuid import UUID

from supabase import Client

logger = logging.getLogger(__name__)


async def criar_ou_retomar_conversa(
    conversa_id: UUID | None,
    usuario_id: str,
    db_admin: Client,
    tenant_id: str | None = None,
) -> str:
    """Retorna o ID da conversa — cria nova se conversa_id for None."""
    if conversa_id:
        resp = db_admin.table("chat_conversas")\
            .select("id")\
            .eq("id", str(conversa_id))\
            .eq("usuario_id", usuario_id)\
            .maybe_single()\
            .execute()
        if resp is not None and getattr(resp, "data", None):
            return str(conversa_id)

    entrada: dict = {"usuario_id": usuario_id}
    if tenant_id:
        entrada["tenant_id"] = tenant_id

    resp = db_admin.table("chat_conversas").insert(entrada).execute()
    return resp.data[0]["id"]


async def carregar_historico(conversa_id: str, db_admin: Client) -> list[dict]:
    """Carrega mensagens anteriores da conversa para montar o contexto."""
    resp = db_admin.table("chat_mensagens")\
        .select("role, conteudo")\
        .eq("conversa_id", conversa_id)\
        .order("criada_em")\
        .execute()

    historico = []
    for msg in (resp.data or []):
        historico.append({"role": msg["role"], "content": msg["conteudo"]})
    return historico


async def salvar_mensagem(
    conversa_id: str,
    role: str,
    conteudo: str,
    tool_calls: list[str] | None,
    db_admin: Client,
) -> None:
    """Persiste uma mensagem (user ou assistant) na conversa."""
    try:
        db_admin.table("chat_mensagens").insert({
            "conversa_id": conversa_id,
            "role":        role,
            "conteudo":    conteudo[:10_000],   # trunca conteúdo muito longo
            "tool_calls":  tool_calls,
        }).execute()

        # Atualiza timestamp da conversa
        db_admin.table("chat_conversas")\
            .update({"atualizada_em": "now()"})\
            .eq("id", conversa_id)\
            .execute()
    except Exception as e:
        logger.warning("Falha ao salvar mensagem no histórico: %s", e)


async def listar_conversas(usuario_id: str, db_admin: Client) -> list[dict]:
    """Lista as conversas do usuário, mais recentes primeiro (max 50)."""
    resp = db_admin.table("chat_conversas")\
        .select("id, titulo, criada_em, atualizada_em")\
        .eq("usuario_id", usuario_id)\
        .order("atualizada_em", desc=True)\
        .limit(50)\
        .execute()
    return resp.data or []


async def atualizar_titulo(
    conversa_id: str,
    titulo: str,
    db_admin: Client,
) -> None:
    """Atualiza o título da conversa (gerado após a primeira resposta)."""
    try:
        db_admin.table("chat_conversas")\
            .update({"titulo": titulo[:200]})\
            .eq("id", conversa_id)\
            .is_("titulo", "null")\
            .execute()
    except Exception as e:
        logger.warning("Falha ao atualizar título da conversa: %s", e)
