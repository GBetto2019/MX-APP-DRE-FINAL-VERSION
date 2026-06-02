"""
MX Seguros — DRE-IA | Conexão com o banco de dados.

asyncpg (direto ao Postgres) é usado quando DATABASE_URL estiver disponível —
40-60% mais rápido que PostgREST. Fallback transparente para supabase-py.
supabase-py permanece para auth.get_user() e audit_log (admin operations).
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncIterator

import asyncpg
from supabase import Client, ClientOptions, create_client

from app.config import cfg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    """Registra codecs JSON/JSONB para que asyncpg retorne dict/list nativamente."""
    await conn.set_type_codec("json",  encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


# ── SUPABASE (Auth, admin operations) ────────────────────────

@lru_cache(maxsize=1)
def get_supabase_admin() -> Client:
    """
    Cliente com service_role — bypassa RLS.
    Usar APENAS para auth.get_user(), audit_log e operações admin do sistema.
    NUNCA para queries de negócio voltadas ao usuário final.
    """
    return create_client(cfg.supabase_url, cfg.supabase_service_role_key)


def get_supabase_anonimo() -> Client:
    return create_client(cfg.supabase_url, cfg.supabase_anon_key)


def get_supabase_usuario(jwt_token: str) -> Client:
    """
    Cliente autenticado com JWT do usuário — fallback quando asyncpg indisponível.
    PostgREST aplica RLS automaticamente via o JWT no header.
    """
    return create_client(
        cfg.supabase_url,
        cfg.supabase_anon_key,
        options=ClientOptions(headers={"Authorization": f"Bearer {jwt_token}"}),
    )


# ── ASYNCPG (business queries, RLS via JWT claims) ────────────

async def init_asyncpg_pool() -> None:
    """Inicializa pool asyncpg no startup da aplicação. No-op se DATABASE_URL ausente."""
    global _pool
    if not cfg.database_url:
        logger.info("DATABASE_URL não definida — usando PostgREST (supabase-py) para queries")
        return
    try:
        _pool = await asyncpg.create_pool(
            cfg.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
            init=_init_conn,
        )
        host = cfg.database_url.split("@")[-1].split("/")[0]
        logger.info("asyncpg pool criado → %s (min=2, max=10)", host)
    except Exception as exc:
        logger.warning("Falha ao criar pool asyncpg: %s — fallback para PostgREST", exc)
        _pool = None


async def close_asyncpg_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool encerrado")


def get_asyncpg_pool() -> asyncpg.Pool | None:
    return _pool


@asynccontextmanager
async def conn_as_user(user_id: str) -> AsyncIterator[asyncpg.Connection]:
    """
    Yields uma conexão asyncpg com RLS ativo para user_id.

    Replica o que o PostgREST faz a cada request:
      1. SET LOCAL ROLE authenticated  — ativa as políticas RLS com TO authenticated
      2. set_config('request.jwt.claims', ...)  — alimenta auth.uid() e helpers SQL

    is_local=true (terceiro arg de set_config) garante que as configs
    se resetam ao fim da transação, impedindo vazamento de JWT entre
    conexões do pool.
    """
    pool = _pool
    if pool is None:
        raise RuntimeError("asyncpg pool não inicializado — configure DATABASE_URL no .env")

    claims = json.dumps({"sub": user_id, "role": "authenticated"})
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE authenticated")
            await conn.execute(
                "SELECT set_config('request.jwt.claims', $1, true)",
                claims,
            )
            yield conn
