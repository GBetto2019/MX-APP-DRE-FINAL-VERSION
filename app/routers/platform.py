"""
MX Seguros — DRE-IA | Router: /platform (super_admin)

Sprint 4 (Task 4.5): Rotas de gestão da plataforma multi-tenant.
Sprint 5: Theming e onboarding por tenant.
Sprint 6: Billing, limites e métricas.

Acesso exclusivo para role = 'super_admin'.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth import UsuarioAtual, obter_usuario_atual
from app.database import get_supabase_admin
from app.logging_config import get_logger
from app.middleware.tenant import invalidar_cache_tenant

logger = get_logger(__name__)
router = APIRouter(prefix="/platform", tags=["Plataforma (super_admin)"])


# ── Guard ────────────────────────────────────────────────────

def _exigir_super_admin(usuario: UsuarioAtual) -> None:
    if usuario.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso exclusivo para super_admin.",
        )


# ── Schemas ──────────────────────────────────────────────────

class TenantCreate(BaseModel):
    nome:              str = Field(min_length=2, max_length=100)
    slug:              str = Field(min_length=2, max_length=50, pattern=r'^[a-z0-9\-]+$')
    plano:             str = Field(default="basico")
    nome_exibicao:     str | None = None
    cor_primaria:      str = Field(default="#1F4E79")
    cor_secundaria:    str = Field(default="#2E86C1")
    max_usuarios:      int = Field(default=5, ge=1, le=10000)
    max_msgs_ia_dia:   int = Field(default=50, ge=0, le=100000)
    max_apolices:      int = Field(default=1000, ge=0)


class TenantUpdate(BaseModel):
    nome:              str | None = None
    plano:             str | None = None
    ativo:             bool | None = None
    bloqueado:         bool | None = None
    bloqueado_motivo:  str | None = None
    cor_primaria:      str | None = None
    cor_secundaria:    str | None = None
    logo_url:          str | None = None
    nome_exibicao:     str | None = None
    max_usuarios:      int | None = Field(default=None, ge=1)
    max_msgs_ia_dia:   int | None = Field(default=None, ge=0)
    max_apolices:      int | None = Field(default=None, ge=0)
    setup_completo:    bool | None = None


class ThemingUpdate(BaseModel):
    """Sprint 5 — Theming por tenant."""
    cor_primaria:    str | None = None
    cor_secundaria:  str | None = None
    logo_url:        str | None = None
    nome_exibicao:   str | None = None


class PlanosLimitesUpdate(BaseModel):
    """Sprint 6 — Limites por plano."""
    plano:            str | None = None
    max_usuarios:     int | None = Field(default=None, ge=1)
    max_msgs_ia_dia:  int | None = Field(default=None, ge=0)
    max_apolices:     int | None = Field(default=None, ge=0)
    bloqueado:        bool | None = None
    bloqueado_motivo: str | None = None
    trial_ate:        date | None = None


# ══════════════════════════════════════════════════════════════
# Sprint 4 — Gestão de Tenants
# ══════════════════════════════════════════════════════════════

@router.get("/tenants", summary="Listar todos os tenants")
async def listar_tenants(
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    _exigir_super_admin(usuario)
    db = get_supabase_admin()
    resp = db.table("tenants") \
        .select("*") \
        .order("criado_em", desc=True) \
        .execute()
    return {"total": len(resp.data or []), "items": resp.data or []}


@router.post("/tenants", summary="Criar novo tenant", status_code=status.HTTP_201_CREATED)
async def criar_tenant(
    payload: TenantCreate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    _exigir_super_admin(usuario)
    db = get_supabase_admin()

    dados = payload.model_dump(exclude_none=True)
    dados["nome_exibicao"] = dados.get("nome_exibicao") or dados["nome"]

    resp = db.table("tenants").insert(dados).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Falha ao criar tenant.")

    tenant = resp.data[0]
    logger.info("tenant_criado", slug=tenant["slug"], plano=tenant["plano"], super_admin=usuario.user_id)
    return tenant


@router.get("/tenants/{tenant_id}", summary="Detalhe de um tenant")
async def get_tenant(
    tenant_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    _exigir_super_admin(usuario)
    db = get_supabase_admin()
    resp = db.table("tenants").select("*").eq("id", str(tenant_id)).maybe_single().execute()
    if not resp or not getattr(resp, "data", None):
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    return resp.data


@router.patch("/tenants/{tenant_id}", summary="Atualizar tenant")
async def atualizar_tenant(
    tenant_id: UUID,
    payload: TenantUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    _exigir_super_admin(usuario)
    dados = payload.model_dump(exclude_none=True)
    if not dados:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")

    db = get_supabase_admin()
    resp = db.table("tenants").update(dados).eq("id", str(tenant_id)).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")

    invalidar_cache_tenant(resp.data[0].get("slug", ""))
    return resp.data[0]


@router.delete("/tenants/{tenant_id}", summary="Desativar tenant (soft-delete)")
async def desativar_tenant(
    tenant_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """Desativa o tenant (ativo=false). Nunca deleta fisicamente."""
    _exigir_super_admin(usuario)
    db = get_supabase_admin()
    resp = db.table("tenants").update({"ativo": False}).eq("id", str(tenant_id)).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    invalidar_cache_tenant(resp.data[0].get("slug", ""))
    return {"desativado": True, "tenant_id": str(tenant_id)}


# ══════════════════════════════════════════════════════════════
# Sprint 5 — Theming e Onboarding por Tenant
# ══════════════════════════════════════════════════════════════

@router.patch("/tenants/{tenant_id}/theming", summary="Atualizar theming do tenant")
async def atualizar_theming(
    tenant_id: UUID,
    payload: ThemingUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """
    Atualiza logo, cores e nome de exibição do tenant.
    Acessível por super_admin ou pelo próprio admin do tenant.
    """
    db = get_supabase_admin()

    # admin do tenant pode atualizar o próprio theming
    if usuario.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito a Admin e Super Admin.")

    dados = payload.model_dump(exclude_none=True)
    if not dados:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")

    resp = db.table("tenants").update(dados).eq("id", str(tenant_id)).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")

    invalidar_cache_tenant(resp.data[0].get("slug", ""))
    logger.info("theming_atualizado", tenant_id=str(tenant_id), usuario_id=usuario.user_id)
    return resp.data[0]


@router.get("/tenants/{tenant_id}/setup-status", summary="Status do setup wizard")
async def setup_status(
    tenant_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """
    Sprint 5 — Setup Wizard: verifica se o tenant completou a configuração inicial.
    Retorna checklist de onboarding.
    """
    db = get_supabase_admin()

    tenant = db.table("tenants").select("*").eq("id", str(tenant_id)).maybe_single().execute()
    if not tenant or not getattr(tenant, "data", None):
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")

    t = tenant.data

    # Verificar se há pelo menos 1 usuário admin cadastrado
    usuarios = db.table("usuarios").select("id", count="exact").eq("tenant_id", str(tenant_id)).eq("role", "admin").execute()
    tem_admin = (usuarios.count or 0) > 0

    # Verificar se há equipes
    equipes = db.table("equipes").select("id", count="exact").eq("tenant_id", str(tenant_id)).execute()
    tem_equipe = (equipes.count or 0) > 0

    checklist = {
        "tenant_criado":     True,
        "theming_configurado": bool(t.get("logo_url") or t.get("nome_exibicao")),
        "admin_cadastrado":  tem_admin,
        "equipe_criada":     tem_equipe,
        "setup_completo":    t.get("setup_completo", False),
    }
    progresso = sum(1 for v in checklist.values() if v)
    total = len(checklist)

    return {
        "tenant_id":  str(tenant_id),
        "checklist":  checklist,
        "progresso":  f"{progresso}/{total}",
        "percentual": round(progresso / total * 100),
    }


@router.post("/tenants/{tenant_id}/setup-completo", summary="Marcar setup como concluído")
async def marcar_setup_completo(
    tenant_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    _exigir_super_admin(usuario)
    db = get_supabase_admin()
    resp = db.table("tenants").update({"setup_completo": True}).eq("id", str(tenant_id)).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    return {"setup_completo": True}


# ══════════════════════════════════════════════════════════════
# Sprint 6 — Billing e Limites
# ══════════════════════════════════════════════════════════════

@router.patch("/tenants/{tenant_id}/plano", summary="Atualizar plano e limites")
async def atualizar_plano(
    tenant_id: UUID,
    payload: PlanosLimitesUpdate,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """Sprint 6 — Gerencia plano, limites de uso e bloqueio do tenant."""
    _exigir_super_admin(usuario)
    dados = payload.model_dump(exclude_none=True)
    if not dados:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")

    db = get_supabase_admin()
    resp = db.table("tenants").update(dados).eq("id", str(tenant_id)).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")

    logger.info("plano_atualizado", tenant_id=str(tenant_id), dados=dados)
    invalidar_cache_tenant(resp.data[0].get("slug", ""))
    return resp.data[0]


@router.get("/dashboard", summary="Dashboard de métricas da plataforma")
async def platform_dashboard(
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """Sprint 6 — Métricas globais da plataforma para super_admin."""
    _exigir_super_admin(usuario)
    db = get_supabase_admin()

    tenants_resp = db.table("tenants").select("id,nome,slug,plano,ativo,bloqueado").execute()
    tenants = tenants_resp.data or []

    usuarios_resp = db.table("usuarios").select("id,tenant_id,role").execute()
    usuarios = usuarios_resp.data or []

    # Agrega por tenant
    stats: dict[str, dict] = {}
    for t in tenants:
        tid = t["id"]
        stats[tid] = {
            "tenant":    t["nome"],
            "slug":      t["slug"],
            "plano":     t["plano"],
            "ativo":     t["ativo"],
            "bloqueado": t["bloqueado"],
            "usuarios":  0,
        }

    for u in usuarios:
        tid = u.get("tenant_id")
        if tid and tid in stats:
            stats[tid]["usuarios"] += 1

    return {
        "total_tenants":   len(tenants),
        "tenants_ativos":  sum(1 for t in tenants if t["ativo"]),
        "total_usuarios":  len(usuarios),
        "por_tenant":      list(stats.values()),
    }


@router.get("/tenants/{tenant_id}/limites", summary="Verificar uso vs. limites do plano")
async def verificar_limites(
    tenant_id: UUID,
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """Sprint 6 — Retorna uso atual vs. limites contratados."""
    if usuario.role not in ("super_admin", "admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito.")

    db = get_supabase_admin()

    # Tenant
    t_resp = db.table("tenants").select("*").eq("id", str(tenant_id)).maybe_single().execute()
    if not t_resp or not getattr(t_resp, "data", None):
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    t = t_resp.data

    # Contagens
    usuarios_count = db.table("usuarios").select("id", count="exact").eq("tenant_id", str(tenant_id)).eq("ativo", True).execute().count or 0
    apolices_count = db.table("apolices").select("id", count="exact").eq("tenant_id", str(tenant_id)).execute().count or 0

    # Msgs IA hoje
    from datetime import date as d
    hoje = d.today().isoformat()
    msgs_hoje = db.table("audit_log").select("id", count="exact").eq("tenant_id", str(tenant_id)).eq("acao", "chat_ia").gte("criado_em", hoje).execute().count or 0

    return {
        "tenant":     t["nome"],
        "plano":      t["plano"],
        "bloqueado":  t["bloqueado"],
        "limites": {
            "usuarios":    {"uso": usuarios_count,  "limite": t["max_usuarios"],    "pct": round(usuarios_count / max(t["max_usuarios"], 1) * 100)},
            "apolices":    {"uso": apolices_count,   "limite": t["max_apolices"],    "pct": round(apolices_count / max(t["max_apolices"], 1) * 100)},
            "msgs_ia_hoje":{"uso": msgs_hoje,        "limite": t["max_msgs_ia_dia"], "pct": round(msgs_hoje / max(t["max_msgs_ia_dia"], 1) * 100)},
        },
    }
