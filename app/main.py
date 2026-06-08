"""
MX Seguros — DRE-IA | Ponto de entrada do backend FastAPI.

Rodar localmente:
    uvicorn app.main:app --reload --port 8000

Swagger UI: http://localhost:8000/docs
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import cfg
from app.database import close_asyncpg_pool, init_asyncpg_pool
from app.logging_config import get_logger, setup_logging
from app.middleware.rate_limit import limiter
from app.middleware.tenant import TenantMiddleware
from app.routers import chat, comissoes, configuracoes, dashboard, dre, estornos, exports, fechamentos, health as health_router, importacao, lancamentos, metas, platform, repasses, usuarios

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_asyncpg_pool()
    yield
    await close_asyncpg_pool()


app = FastAPI(
    lifespan=lifespan,
    title="MX Seguros — DRE-IA API",
    description=(
        "Backend do sistema de DRE com IA para a MX Seguros. "
        "Todos os endpoints exigem JWT do Supabase Auth no header Authorization."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── RATE LIMITING ─────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────
_frontend_urls_dev = ["http://localhost:3000", "http://localhost:3001"]
_frontend_url_prod = os.getenv("FRONTEND_URL", "https://app.mxseguros.com.br")

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        _frontend_urls_dev
        if not cfg.is_production
        else [_frontend_url_prod]
    ),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── TENANT MIDDLEWARE ─────────────────────────────────────────
app.add_middleware(TenantMiddleware)

# ── SECURITY HEADERS ──────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if cfg.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ── ROUTERS ───────────────────────────────────────────────────

app.include_router(health_router.router)
app.include_router(platform.router)
app.include_router(dashboard.router)
app.include_router(chat.router)
app.include_router(dre.router)
app.include_router(exports.router)
app.include_router(comissoes.router)
app.include_router(estornos.router)
app.include_router(metas.router)
app.include_router(repasses.router)
app.include_router(lancamentos.router)
app.include_router(fechamentos.router)
app.include_router(importacao.router)
app.include_router(configuracoes.router)
app.include_router(usuarios.router)



# ── HANDLER GLOBAL DE ERROS ───────────────────────────────────

@app.exception_handler(Exception)
async def handler_global(request: Request, exc: Exception):
    logger.error(
        "erro_nao_tratado",
        path=request.url.path,
        method=request.method,
        exc=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"erro": "Erro interno do servidor", "detalhe": str(exc) if not cfg.is_production else None},
    )
