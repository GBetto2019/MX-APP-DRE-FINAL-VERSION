"""
Middleware de resolução de tenant — Sprint 4.

Estratégia de resolução (ordem de prioridade):
1. Header X-Tenant-Slug (para API direta e testes)
2. Subdomínio da URL (ex: mx-seguros.dreapp.com.br → slug 'mx-seguros')
3. Fallback: slug 'mx-seguros' (tenant padrão em dev/monolítico)

O tenant é colocado em request.state.tenant_id para uso nos serviços.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import get_logger

logger = get_logger(__name__)

_TENANT_PADRAO_SLUG = "mx-seguros"


@lru_cache(maxsize=128)
def _slug_para_id(slug: str) -> str | None:
    """Cache: slug → tenant_id. Retorna None se tabela não existir (migration pendente)."""
    from app.database import get_supabase_admin
    try:
        db = get_supabase_admin()
        resp = db.table("tenants") \
            .select("id") \
            .eq("slug", slug) \
            .eq("ativo", True) \
            .maybe_single() \
            .execute()
        if resp is not None and getattr(resp, "data", None):
            return resp.data["id"]
        return None
    except Exception as e:
        err = str(e)
        # Graceful degradation: se a tabela tenants não existir ainda (migration pendente),
        # não bloqueia — retorna sentinel que bypassa o check de tenant
        if "schema cache" in err or "does not exist" in err or "PGRST205" in err:
            logger.debug("tenant_table_nao_existe_ainda", slug=slug)
            return _BYPASS_SENTINEL
        logger.warning("tenant_lookup_falhou", slug=slug, erro=err)
        return None


_BYPASS_SENTINEL = "bypass-migration-pendente"


def _extrair_slug(request: Request) -> str:
    """Extrai o slug do tenant do header ou subdomínio."""
    # 1. Header explícito
    slug = request.headers.get("X-Tenant-Slug", "").strip()
    if slug:
        return slug

    # 2. Subdomínio (ex: mx-seguros.dreapp.com.br)
    host = request.headers.get("host", "")
    partes = host.split(".")
    if len(partes) >= 3:
        possivel_slug = partes[0]
        # Exclui subdomínios de infra
        if possivel_slug not in ("www", "api", "app", "admin", "localhost"):
            return possivel_slug

    return _TENANT_PADRAO_SLUG


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Resolve o tenant por slug e injeta tenant_id em request.state.
    Rotas públicas (/health, /docs, /redoc, /openapi.json) ignoram.
    Hosts de infra (vercel.app, railway.app, etc.) também ignoram — tenant_id = None.
    """

    _ROTAS_PUBLICAS = {"/health", "/docs", "/redoc", "/openapi.json", "/platform"}
    _INFRA_HOSTS    = (".vercel.app", ".railway.app", ".render.com", ".fly.dev", ".onrender.com")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Ignora rotas públicas e prefixos de plataforma
        if any(path.startswith(r) for r in self._ROTAS_PUBLICAS):
            request.state.tenant_id = None
            return await call_next(request)

        host = request.headers.get("host", "")

        # Hosts de infra / localhost: sem resolução de tenant
        if any(host.endswith(h) for h in self._INFRA_HOSTS) or host.startswith("localhost"):
            request.state.tenant_id = None
            return await call_next(request)

        slug = _extrair_slug(request)
        tenant_id = _slug_para_id(slug)

        if tenant_id is None:
            logger.warning("tenant_nao_encontrado", slug=slug, path=path)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"erro": f"Tenant '{slug}' não encontrado ou inativo."},
            )

        # Se migration ainda não aplicada, permite passar sem tenant_id
        if tenant_id == _BYPASS_SENTINEL:
            request.state.tenant_id = None
        else:
            request.state.tenant_id = tenant_id
        logger.debug("tenant_resolvido", slug=slug, tenant_id=tenant_id, path=path)

        return await call_next(request)


def invalidar_cache_tenant(slug: str | None = None) -> None:
    """Invalida todo o cache de tenant (lru_cache não suporta invalidação por chave)."""
    _slug_para_id.cache_clear()
