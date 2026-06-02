"""
MX Seguros — DRE-IA | Serviço de Fechamentos Mensais.

Um fechamento captura um snapshot completo do DRE (visão admin, sem filtro
de perfil) e marca o período como encerrado.

Regras:
- Só pode haver um fechamento ATIVO (não reaberto) por mês — partial unique index.
- Reabertura mantém o registro histórico; novo fechamento pode ser criado depois.
- O snapshot usa db_admin (service_role) para capturar todos os valores sem RLS.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status as http_status
from supabase import Client

from app.auth import UsuarioAtual
from app.models.schemas import FechamentoItem, FechamentosResponse

logger = logging.getLogger(__name__)


def _ultimo_dia(competencia: date) -> date:
    last = calendar.monthrange(competencia.year, competencia.month)[1]
    return date(competencia.year, competencia.month, last)


async def listar_fechamentos(db: Client) -> FechamentosResponse:
    resp = (
        db.table("fechamentos")
        .select("*")
        .order("competencia", desc=True)
        .execute()
    )
    items = [FechamentoItem(**r) for r in (resp.data or [])]
    return FechamentosResponse(total=len(items), items=items)


async def criar_fechamento(
    competencia: date,
    usuario: UsuarioAtual,
    db: Client,
    db_admin: Client,
) -> FechamentoItem:
    # competencia sempre no primeiro dia do mês (validado no schema, mas reforça aqui)
    competencia = date(competencia.year, competencia.month, 1)

    # Verifica se já existe fechamento ativo para este mês
    existe = (
        db.table("fechamentos")
        .select("id")
        .eq("competencia", competencia.isoformat())
        .is_("reaberto_em", "null")
        .execute()
    )
    if existe.data:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Mês {competencia.strftime('%m/%Y')} já possui fechamento ativo.",
        )

    # Gera snapshot via admin (sem filtro de perfil — captura DRE completo)
    fim = _ultimo_dia(competencia)
    try:
        resp_dre = db_admin.rpc("dre_por_periodo", {
            "p_inicio": competencia.isoformat(),
            "p_fim":    fim.isoformat(),
        }).execute()
        snapshot = resp_dre.data or {}
    except Exception as exc:
        logger.error("Falha ao gerar snapshot DRE para fechamento: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao gerar snapshot do DRE.",
        )

    agora = datetime.now(timezone.utc).isoformat()
    entrada = {
        "competencia":  competencia.isoformat(),
        "fechado_por":  usuario.user_id,
        "fechado_em":   agora,
        "snapshot_dre": snapshot,
    }
    if getattr(usuario, "tenant_id", None):
        entrada["tenant_id"] = usuario.tenant_id

    resp = db.table("fechamentos").insert(entrada).execute()

    if not resp.data:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao persistir fechamento.",
        )
    return FechamentoItem(**resp.data[0])


async def reabrir_fechamento(
    fechamento_id: UUID,
    motivo: str,
    usuario: UsuarioAtual,
    db: Client,
) -> FechamentoItem:
    if not motivo or not motivo.strip():
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Motivo de reabertura é obrigatório.",
        )

    agora = datetime.now(timezone.utc).isoformat()
    resp = (
        db.table("fechamentos")
        .update({
            "reaberto_por":    usuario.user_id,
            "reaberto_em":     agora,
            "reaberto_motivo": motivo.strip(),
        })
        .eq("id", str(fechamento_id))
        .is_("reaberto_em", "null")   # só reabre se ainda estiver ativo
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Fechamento não encontrado ou já reaberto.",
        )
    return FechamentoItem(**resp.data[0])
