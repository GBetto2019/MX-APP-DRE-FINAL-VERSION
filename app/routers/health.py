"""MX Seguros — DRE-IA | Router: /health"""
from __future__ import annotations

import time as _time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import UsuarioAtual, obter_usuario_atual
from app.config import cfg

router = APIRouter(tags=["Sistema"])

_APP_VERSION = "1.2.0"
_startup_time = _time.monotonic()


@router.get("/health", summary="Health check público")
async def health():
    """Endpoint de status para uptime monitors (Uptime Robot, Betterstack, etc.)."""
    from app.database import get_supabase_admin
    db_ok = True
    try:
        get_supabase_admin().table("usuarios").select("id").limit(1).execute()
    except Exception:
        db_ok = False

    return {
        "status":         "healthy" if db_ok else "degraded",
        "version":        _APP_VERSION,
        "ambiente":       cfg.environment,
        "db":             "connected" if db_ok else "error",
        "uptime_seconds": int(_time.monotonic() - _startup_time),
    }


@router.get("/health/detailed", summary="Health check detalhado (admin/contador)")
async def health_detailed(
    usuario: Annotated[UsuarioAtual, Depends(obter_usuario_atual)],
):
    """Métricas internas — requer token de admin ou contador."""
    if usuario.role not in ("admin", "contador"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a Admin e Contador.",
        )

    pool_info: dict = {}
    try:
        from app.database import get_asyncpg_pool
        pool = get_asyncpg_pool()
        if pool:
            pool_info = {
                "pool_size": pool.get_size(),
                "pool_idle": pool.get_idle_size(),
                "pool_min":  pool.get_min_size(),
            }
    except Exception:
        pool_info = {"status": "n/a"}

    return {
        "status":         "healthy",
        "version":        _APP_VERSION,
        "ambiente":       cfg.environment,
        "uptime_seconds": int(_time.monotonic() - _startup_time),
        "asyncpg_pool":   pool_info,
        "supabase_url":   cfg.supabase_url,
        "usuario_role":   usuario.role,
    }
