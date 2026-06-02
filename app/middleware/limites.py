"""
Sprint 6 — Validação de limites por plano.
Verifica se o tenant está bloqueado e se o limite de mensagens de IA foi atingido.
"""
from __future__ import annotations

from fastapi import HTTPException, status

from app.logging_config import get_logger

logger = get_logger(__name__)


async def verificar_tenant_ativo(tenant_id: str | None) -> None:
    """Lança 403 se o tenant estiver bloqueado."""
    if not tenant_id:
        return
    from app.database import get_supabase_admin
    db = get_supabase_admin()
    resp = db.table("tenants").select("bloqueado,bloqueado_motivo,ativo").eq("id", tenant_id).maybe_single().execute()
    if not resp or not getattr(resp, "data", None):
        return
    t = resp.data
    if not t.get("ativo"):
        raise HTTPException(status_code=403, detail="Tenant inativo.")
    if t.get("bloqueado"):
        motivo = t.get("bloqueado_motivo") or "Tenant bloqueado."
        raise HTTPException(status_code=402, detail=motivo)


async def verificar_limite_msgs_ia(tenant_id: str | None, usuario_id: str) -> None:
    """Lança 429 se o limite diário de mensagens de IA foi atingido."""
    if not tenant_id:
        return
    from datetime import date
    from app.database import get_supabase_admin
    db = get_supabase_admin()

    # Buscar limite do plano
    t = db.table("tenants").select("max_msgs_ia_dia").eq("id", tenant_id).maybe_single().execute()
    if not t or not getattr(t, "data", None):
        return
    limite = t.data.get("max_msgs_ia_dia", 50)
    if limite == 0:
        return  # ilimitado

    # Contar msgs hoje do tenant
    hoje = date.today().isoformat()
    uso = db.table("audit_log").select("id", count="exact") \
        .eq("tenant_id", tenant_id) \
        .eq("acao", "chat_ia") \
        .gte("criado_em", hoje) \
        .execute()
    total = uso.count or 0

    if total >= limite:
        logger.warning("limite_ia_atingido", tenant_id=tenant_id, uso=total, limite=limite)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Limite diário de {limite} mensagens de IA atingido. Tente amanhã.",
        )
