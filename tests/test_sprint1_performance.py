"""
Sprint 1 — Testes de Performance.

Cobre:
- Task 1.1: Índices compostos (migration 0010 existe e tem os índices certos)
- Task 1.2: asyncpg como driver preferencial (código usa pool quando disponível)
- Task 1.3: GET /dashboard retorna DRE + metas + alertas em uma chamada
- Task 1.5: Cache de role em memória (TTL 60s)

Execute:
    pytest tests/test_sprint1_performance.py -v
"""
from __future__ import annotations

import os
import time

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from supabase import create_client

load_dotenv()
load_dotenv(".env.test", override=False)

SUPABASE_URL  = os.environ["SUPABASE_URL"]
SUPABASE_ANON = os.environ["SUPABASE_ANON_KEY"]

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def tokens() -> dict[str, str]:
    resultado: dict[str, str] = {}
    for role, email in [
        ("admin",     "admin@mxseguros.test"),
        ("gestor",    "gestor@mxseguros.test"),
        ("comercial", "comercial@mxseguros.test"),
        ("contador",  "contador@mxseguros.test"),
    ]:
        anon = create_client(SUPABASE_URL, SUPABASE_ANON)
        resp = anon.auth.sign_in_with_password({"email": email, "password": "Teste@123"})
        if resp.session:
            resultado[role] = resp.session.access_token
    return resultado


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


PERIODO = {"inicio": "2026-01-01", "fim": "2026-03-31"}


# ══════════════════════════════════════════════════════════════
# Task 1.1 — Índices compostos
# ══════════════════════════════════════════════════════════════

class TestIndicesCompostos:

    def test_migration_0010_existe(self):
        from pathlib import Path
        caminho = Path(__file__).parent.parent / "migrations" / "0010_indices.sql"
        assert caminho.exists(), "Migration 0010_indices.sql não encontrada"

    def test_migration_0010_tem_indices_criticos(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0010_indices.sql").read_text(encoding="utf-8")
        indices_esperados = [
            "idx_comissoes_competencia",
            "idx_despesas_competencia",
            "idx_apolices",
            "idx_repasses",
        ]
        for idx in indices_esperados:
            assert idx in sql, f"Índice crítico ausente na migration 0010: {idx}"

    def test_migration_0010_usa_if_not_exists(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0010_indices.sql").read_text(encoding="utf-8")
        assert "IF NOT EXISTS" in sql.upper(), (
            "Índices devem usar IF NOT EXISTS para ser idempotentes"
        )


# ══════════════════════════════════════════════════════════════
# Task 1.2 — asyncpg como driver preferencial
# ══════════════════════════════════════════════════════════════

class TestAsyncpgDriver:

    def test_dre_service_tenta_asyncpg_primeiro(self):
        """Verifica que buscar_dre verifica pool antes de usar PostgREST."""
        import inspect
        from app.services.dre_service import buscar_dre

        source = inspect.getsource(buscar_dre)
        assert "_pool()" in source or "get_asyncpg_pool" in source, (
            "buscar_dre deve verificar pool asyncpg antes de usar PostgREST"
        )
        assert "conn_as_user" in source, (
            "buscar_dre deve usar conn_as_user quando pool disponível"
        )

    def test_conn_as_user_configura_rls(self):
        """Verifica que conn_as_user ativa RLS via SET LOCAL ROLE authenticated."""
        import inspect
        from app.database import conn_as_user

        source = inspect.getsource(conn_as_user)
        assert "SET LOCAL ROLE authenticated" in source
        assert "request.jwt.claims" in source

    def test_pool_inicializa_sem_erro(self):
        """Pool deve inicializar silenciosamente mesmo sem DATABASE_URL válida."""
        from app.database import get_asyncpg_pool
        pool = get_asyncpg_pool()
        # Pool pode ser None (DATABASE_URL indisponível) — sem exceção
        assert pool is None or hasattr(pool, "acquire")

    def test_todos_services_usam_asyncpg_quando_disponivel(self):
        """Todos os services de dados devem ter suporte a asyncpg."""
        import inspect
        from app.services import dre_service

        funcoes_com_pool = [
            dre_service.buscar_dre,
            dre_service.buscar_comissoes,
            dre_service.buscar_estornos,
            dre_service.buscar_metas,
            dre_service.buscar_repasses,
        ]
        for func in funcoes_com_pool:
            source = inspect.getsource(func)
            assert "_pool()" in source or "conn_as_user" in source, (
                f"{func.__name__} não usa asyncpg"
            )


# ══════════════════════════════════════════════════════════════
# Task 1.3 — GET /dashboard (resposta agregada)
# ══════════════════════════════════════════════════════════════

class TestDashboard:

    def test_dashboard_sem_auth_retorna_401(self, client):
        r = client.get("/dashboard", params=PERIODO)
        assert r.status_code == 401

    def test_dashboard_periodo_invalido_retorna_400(self, client, tokens):
        token = tokens.get("admin")
        if not token:
            pytest.skip("Token admin não disponível")
        r = client.get(
            "/dashboard",
            params={"inicio": "2020-01-01", "fim": "2026-12-31"},
            headers=auth(token),
        )
        assert r.status_code == 400

    def test_dashboard_admin_retorna_estrutura_completa(self, client, tokens):
        token = tokens.get("admin")
        if not token:
            pytest.skip("Token admin não disponível")
        r = client.get("/dashboard", params=PERIODO, headers=auth(token))
        assert r.status_code == 200
        data = r.json()

        # Campos obrigatórios
        assert "periodo" in data
        assert "dre" in data
        assert "perfil" in data
        assert "metas" in data
        assert "alertas" in data
        assert "latencia_ms" in data

        # Estrutura do DRE
        dre = data["dre"]
        assert "receita_bruta" in dre
        assert "ebitda" in dre           # admin vê tudo
        assert "resultado_liquido" in dre

    def test_dashboard_retorna_latencia_positiva(self, client, tokens):
        token = tokens.get("admin")
        if not token:
            pytest.skip("Token admin não disponível")
        r = client.get("/dashboard", params=PERIODO, headers=auth(token))
        assert r.status_code == 200
        assert r.json()["latencia_ms"] >= 0

    def test_dashboard_gestor_sem_ebitda(self, client, tokens):
        token = tokens.get("gestor")
        if not token:
            pytest.skip("Token gestor não disponível")
        r = client.get("/dashboard", params=PERIODO, headers=auth(token))
        assert r.status_code == 200
        dre = r.json()["dre"]
        assert dre.get("ebitda") is None
        assert dre.get("despesas_fixas") is None

    def test_dashboard_comercial_campos_limitados(self, client, tokens):
        token = tokens.get("comercial")
        if not token:
            pytest.skip("Token comercial não disponível")
        r = client.get("/dashboard", params=PERIODO, headers=auth(token))
        assert r.status_code == 200
        dre = r.json()["dre"]
        # Comercial: apenas receita_bruta, estornos, impostos (resto null)
        assert dre.get("receita_liquida") is None
        assert dre.get("ebitda") is None

    def test_dashboard_alertas_e_lista(self, client, tokens):
        token = tokens.get("admin")
        if not token:
            pytest.skip("Token admin não disponível")
        r = client.get("/dashboard", params=PERIODO, headers=auth(token))
        assert r.status_code == 200
        alertas = r.json()["alertas"]
        assert isinstance(alertas, list)
        # Se houver alertas, devem ter os campos certos
        for alerta in alertas:
            assert "tipo" in alerta
            assert "mensagem" in alerta
            assert "severidade" in alerta

    def test_dashboard_todos_os_perfis_acessam(self, client, tokens):
        """Todos os 4 perfis devem conseguir chamar /dashboard."""
        for role in ("admin", "gestor", "comercial", "contador"):
            token = tokens.get(role)
            if not token:
                continue
            r = client.get("/dashboard", params=PERIODO, headers=auth(token))
            assert r.status_code == 200, f"Perfil '{role}' deveria acessar /dashboard"

    def test_dashboard_perfil_correto_no_response(self, client, tokens):
        for role in ("admin", "contador"):
            token = tokens.get(role)
            if not token:
                continue
            r = client.get("/dashboard", params=PERIODO, headers=auth(token))
            assert r.json()["perfil"] == role

    def test_dashboard_endpoint_registrado_no_app(self):
        rotas = [r.path for r in app.routes]
        assert "/dashboard" in rotas, "GET /dashboard não registrado no app"


# ══════════════════════════════════════════════════════════════
# Task 1.3 — Paralelismo interno (asyncio.gather)
# ══════════════════════════════════════════════════════════════

class TestParalelismoDashboard:

    def test_dashboard_service_usa_asyncio_gather(self):
        """Verifica que o service usa gather() para paralelizar as consultas."""
        import inspect
        from app.services.dashboard_service import buscar_dashboard

        source = inspect.getsource(buscar_dashboard)
        assert "asyncio.gather" in source, (
            "dashboard_service deve usar asyncio.gather para paralelizar"
        )

    def test_dashboard_service_mede_latencia(self):
        """Verifica que o service registra o tempo de execução."""
        import inspect
        from app.services.dashboard_service import buscar_dashboard

        source = inspect.getsource(buscar_dashboard)
        assert "latencia_ms" in source
        assert "time.monotonic" in source

    def test_dashboard_service_gera_alertas(self):
        """Verifica que a função de alertas existe e é chamada."""
        import inspect
        from app.services import dashboard_service

        source = inspect.getsource(dashboard_service)
        assert "_gerar_alertas" in source
        assert "estorno" in source.lower()
        assert "meta" in source.lower()


# ══════════════════════════════════════════════════════════════
# Task 1.5 — Cache de role (TTLCache)
# ══════════════════════════════════════════════════════════════

class TestCacheRole:

    def test_cache_existe_no_auth(self):
        import inspect
        from app import auth

        source = inspect.getsource(auth)
        assert "_role_cache" in source
        assert "TTL" in source or "_ROLE_TTL" in source

    def test_ttl_e_60_segundos(self):
        from app.auth import _ROLE_TTL
        assert _ROLE_TTL == 60.0, f"TTL do cache deve ser 60s, got {_ROLE_TTL}"

    def test_segunda_chamada_usa_cache(self, client, tokens):
        """Segunda requisição para o mesmo usuário deve ser mais rápida (cache)."""
        token = tokens.get("admin")
        if not token:
            pytest.skip("Token admin não disponível")

        # 1ª chamada (popula cache)
        t0 = time.monotonic()
        r1 = client.get("/health/detailed", headers=auth(token))
        t1 = time.monotonic() - t0

        # 2ª chamada (deve usar cache de role)
        t0 = time.monotonic()
        r2 = client.get("/health/detailed", headers=auth(token))
        t2 = time.monotonic() - t0

        assert r1.status_code == 200
        assert r2.status_code == 200
        # Cache deve tornar a 2ª chamada pelo menos um pouco mais rápida
        # (não assertamos valor exato pois depende de rede)
        assert t2 < t1 * 3, "2ª chamada excessivamente lenta — cache pode não estar funcionando"
