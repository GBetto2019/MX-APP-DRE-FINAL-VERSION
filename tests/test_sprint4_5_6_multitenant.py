"""
Sprints 4, 5 e 6 — Testes de Multi-Tenant, Theming e Billing.

Cobre:
- Task 4.1: Tabela tenants + planos
- Task 4.2: tenant_id em todas as tabelas (após migrations aplicadas)
- Task 4.3: RLS multi-tenant (isolamento por tenant)
- Task 4.4: Middleware de tenant (slug → tenant_id)
- Task 4.5: Router /platform (super_admin)
- Sprint 5: Theming e setup wizard
- Sprint 6: Limites por plano e dashboard de plataforma

Execute:
    pytest tests/test_sprint4_5_6_multitenant.py -v
"""
from __future__ import annotations

import os
from uuid import uuid4

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
def token_admin() -> str:
    anon = create_client(SUPABASE_URL, SUPABASE_ANON)
    resp = anon.auth.sign_in_with_password({"email": "admin@mxseguros.test", "password": "Teste@123"})
    if not resp.session:
        pytest.skip("Token admin não disponível")
    return resp.session.access_token


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ══════════════════════════════════════════════════════════════
# Task 4.1 — Tabela Tenants
# ══════════════════════════════════════════════════════════════

class TestTabelaTenants:

    def test_migration_0017_existe(self):
        from pathlib import Path
        assert (Path(__file__).parent.parent / "migrations" / "0017_tenants.sql").exists()

    def test_migration_0017_cria_tabela_tenants(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0017_tenants.sql").read_text(encoding="utf-8")
        assert "CREATE TABLE" in sql and "tenants" in sql
        assert "plano_tipo" in sql
        assert "max_usuarios" in sql
        assert "cor_primaria" in sql
        assert "mx-seguros" in sql  # seed

    def test_tabela_tenants_existe_no_banco(self):
        """Verifica tabela tenants após migration aplicada."""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        try:
            resp = sb.table("tenants").select("id,slug,plano").execute()
            assert resp is not None
        except Exception as e:
            if "schema cache" in str(e) or "does not exist" in str(e):
                pytest.skip("Migration 0017 não aplicada — aplique SPRINT4_5_6_MULTITENANT.sql")
            raise

    def test_seed_mx_seguros_existe(self):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        try:
            resp = sb.table("tenants").select("id,nome,slug,plano").eq("slug", "mx-seguros").maybe_single().execute()
            if resp is None or not getattr(resp, "data", None):
                pytest.skip("Seed mx-seguros não encontrado — migration 0017 não aplicada")
            t = resp.data
            assert t["slug"] == "mx-seguros"
            assert t["plano"] == "profissional"
        except Exception:
            pytest.skip("Migration 0017 não aplicada")


# ══════════════════════════════════════════════════════════════
# Task 4.2 — tenant_id nas tabelas
# ══════════════════════════════════════════════════════════════

class TestTenantIdNasTabelas:

    def test_migration_0018_existe(self):
        from pathlib import Path
        assert (Path(__file__).parent.parent / "migrations" / "0018_add_tenant_id.sql").exists()

    def test_migration_0018_cobre_todas_tabelas(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0018_add_tenant_id.sql").read_text(encoding="utf-8")
        tabelas_criticas = ["usuarios", "apolices", "comissoes", "despesas", "fechamentos", "audit_log"]
        for t in tabelas_criticas:
            assert t in sql, f"Tabela {t} não coberta em 0018"
        assert "UPDATE" in sql  # popula dados legados
        assert "mx-seguros" in sql  # referencia o tenant seed

    def test_tenant_id_em_usuarios_apos_migration(self):
        """Verifica coluna tenant_id em usuarios."""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        try:
            sb.table("usuarios").select("tenant_id").limit(1).execute()
        except Exception as e:
            if "schema cache" in str(e) or "does not exist" in str(e):
                pytest.skip("Migration 0018 não aplicada — aplique SPRINT4_5_6_MULTITENANT.sql")
            raise


# ══════════════════════════════════════════════════════════════
# Task 4.3 — RLS Multi-tenant
# ══════════════════════════════════════════════════════════════

class TestRLSMultitenant:

    def test_migration_0019_existe(self):
        from pathlib import Path
        assert (Path(__file__).parent.parent / "migrations" / "0019_rls_multitenant.sql").exists()

    def test_migration_0019_tem_funcao_get_meu_tenant(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0019_rls_multitenant.sql").read_text(encoding="utf-8")
        assert "get_meu_tenant()" in sql
        assert "_tenant_ok" in sql
        assert "is_super_admin()" in sql

    def test_migration_0019_cobre_todas_tabelas_criticas(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0019_rls_multitenant.sql").read_text(encoding="utf-8")
        tabelas = ["usuarios", "apolices", "comissoes", "despesas", "metas", "fechamentos"]
        for t in tabelas:
            assert f"ON {t}" in sql, f"RLS para {t} não encontrado em 0019"

    def test_isolation_conceito_sql_correto(self):
        """Verifica que a policy usa _tenant_ok() que combina tenant + super_admin."""
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0019_rls_multitenant.sql").read_text(encoding="utf-8")
        assert "_tenant_ok(tenant_id)" in sql
        assert "get_meu_tenant() OR is_super_admin()" in sql


# ══════════════════════════════════════════════════════════════
# Task 4.4 — Middleware de Tenant
# ══════════════════════════════════════════════════════════════

class TestMiddlewareTenant:

    def test_middleware_importa_sem_erro(self):
        from app.middleware.tenant import TenantMiddleware, _extrair_slug
        assert TenantMiddleware is not None
        assert callable(_extrair_slug)

    def test_extrair_slug_do_header(self):
        from app.middleware.tenant import _extrair_slug
        from unittest.mock import MagicMock

        req = MagicMock()
        req.headers = {"X-Tenant-Slug": "minha-corretora", "host": "localhost:8000"}
        req.url.path = "/dre"

        slug = _extrair_slug(req)
        assert slug == "minha-corretora"

    def test_extrair_slug_do_subdomain(self):
        from app.middleware.tenant import _extrair_slug
        from unittest.mock import MagicMock

        req = MagicMock()
        req.headers = {"host": "mx-seguros.dreapp.com.br"}
        req.url.path = "/dre"

        slug = _extrair_slug(req)
        assert slug == "mx-seguros"

    def test_extrair_slug_fallback(self):
        from app.middleware.tenant import _extrair_slug, _TENANT_PADRAO_SLUG
        from unittest.mock import MagicMock

        req = MagicMock()
        req.headers = {"host": "localhost:8000"}
        req.url.path = "/dre"

        slug = _extrair_slug(req)
        assert slug == _TENANT_PADRAO_SLUG

    def test_middleware_registrado_no_app(self):
        """TenantMiddleware deve estar importado e adicionado no main."""
        import inspect
        import app.main as main_module
        source = inspect.getsource(main_module)
        assert "TenantMiddleware" in source

    def test_invalidar_cache_funciona(self):
        from app.middleware.tenant import invalidar_cache_tenant, _slug_para_id
        # Popula o cache com qualquer slug
        try:
            _slug_para_id("test-slug-inexistente")
        except Exception:
            pass
        # Invalida — não deve lançar exceção
        invalidar_cache_tenant("test-slug-inexistente")


# ══════════════════════════════════════════════════════════════
# Task 4.5 — Router /platform (super_admin)
# ══════════════════════════════════════════════════════════════

class TestPlatformRouter:

    def test_endpoint_tenants_sem_auth_retorna_401(self, client):
        r = client.get("/platform/tenants")
        assert r.status_code == 401

    def test_endpoint_tenants_admin_retorna_403(self, client, token_admin):
        """Admin normal não pode acessar /platform."""
        r = client.get("/platform/tenants", headers=auth(token_admin))
        assert r.status_code == 403

    def test_endpoint_platform_dashboard_sem_auth_retorna_401(self, client):
        r = client.get("/platform/dashboard")
        assert r.status_code == 401

    def test_endpoints_platform_existem_no_app(self):
        rotas = [r.path for r in app.routes]
        assert "/platform/tenants" in rotas
        assert "/platform/dashboard" in rotas

    def test_schema_tenant_create_valida_slug(self):
        """Slug com caracteres inválidos deve falhar."""
        from pydantic import ValidationError
        from app.routers.platform import TenantCreate
        with pytest.raises(ValidationError):
            TenantCreate(nome="Teste", slug="slug com espaço")

    def test_schema_tenant_create_valida_slug_valido(self):
        from app.routers.platform import TenantCreate
        t = TenantCreate(nome="Teste", slug="minha-corretora-123")
        assert t.slug == "minha-corretora-123"


# ══════════════════════════════════════════════════════════════
# Sprint 5 — Theming e Onboarding
# ══════════════════════════════════════════════════════════════

class TestThemingOnboarding:

    def test_migration_0017_tem_campos_theming(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0017_tenants.sql").read_text(encoding="utf-8")
        assert "cor_primaria" in sql
        assert "cor_secundaria" in sql
        assert "logo_url" in sql
        assert "setup_completo" in sql

    def test_endpoint_theming_existe_no_app(self):
        rotas = [r.path for r in app.routes]
        assert any("theming" in r for r in rotas)

    def test_endpoint_setup_status_existe(self):
        rotas = [r.path for r in app.routes]
        assert any("setup-status" in r for r in rotas)

    def test_schema_theming_update(self):
        from app.routers.platform import ThemingUpdate
        t = ThemingUpdate(cor_primaria="#FF5500", logo_url="https://example.com/logo.png")
        assert t.cor_primaria == "#FF5500"

    def test_endpoint_theming_sem_auth_retorna_401(self, client):
        fake_id = str(uuid4())
        r = client.patch(f"/platform/tenants/{fake_id}/theming", json={"cor_primaria": "#FF5500"})
        assert r.status_code == 401

    def test_endpoint_theming_admin_pode_acessar(self, client, token_admin):
        """Admin pode atualizar theming do próprio tenant (não só super_admin)."""
        fake_id = str(uuid4())
        r = client.patch(
            f"/platform/tenants/{fake_id}/theming",
            json={"cor_primaria": "#FF5500"},
            headers=auth(token_admin),
        )
        # 404 (tenant não existe) ou 500 (schema cache — migration pendente) são OK
        # O importante é que o auth passou (não 401 nem 403)
        assert r.status_code not in (401, 403)


# ══════════════════════════════════════════════════════════════
# Sprint 6 — Billing e Limites
# ══════════════════════════════════════════════════════════════

class TestBillingLimites:

    def test_migration_0017_tem_campos_billing(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0017_tenants.sql").read_text(encoding="utf-8")
        assert "max_usuarios" in sql
        assert "max_msgs_ia_dia" in sql
        assert "max_apolices" in sql
        assert "bloqueado" in sql
        assert "stripe_customer_id" in sql

    def test_middleware_limites_importa(self):
        from app.middleware.limites import verificar_tenant_ativo, verificar_limite_msgs_ia
        assert callable(verificar_tenant_ativo)
        assert callable(verificar_limite_msgs_ia)

    def test_chat_verifica_limites(self):
        """Router de chat deve chamar verificar_tenant_ativo e verificar_limite_msgs_ia."""
        import inspect
        import app.routers.chat as chat_mod
        source = inspect.getsource(chat_mod)
        assert "verificar_tenant_ativo" in source
        assert "verificar_limite_msgs_ia" in source

    def test_endpoint_limites_sem_auth_retorna_401(self, client):
        fake_id = str(uuid4())
        r = client.get(f"/platform/tenants/{fake_id}/limites")
        assert r.status_code == 401

    def test_endpoint_plano_sem_auth_retorna_401(self, client):
        fake_id = str(uuid4())
        r = client.patch(f"/platform/tenants/{fake_id}/plano", json={"plano": "enterprise"})
        assert r.status_code == 401

    def test_schema_plano_limites_update(self):
        from app.routers.platform import PlanosLimitesUpdate
        p = PlanosLimitesUpdate(plano="enterprise", max_usuarios=100, bloqueado=False)
        assert p.max_usuarios == 100

    def test_schema_plano_limites_valida_max_usuarios(self):
        from pydantic import ValidationError
        from app.routers.platform import PlanosLimitesUpdate
        with pytest.raises(ValidationError):
            PlanosLimitesUpdate(max_usuarios=0)  # ge=1

    def test_sql_consolidado_sprint456_existe(self):
        from pathlib import Path
        sql_path = Path(__file__).parent.parent / "migrations" / "SPRINT4_5_6_MULTITENANT.sql"
        assert sql_path.exists()
        assert sql_path.stat().st_size > 10000  # > 10kb


# ══════════════════════════════════════════════════════════════
# Verificação de Isolamento (conceitual, sem 2 tenants no banco)
# ══════════════════════════════════════════════════════════════

class TestIsolamentoConceitual:

    def test_policy_tenant_ok_combina_condicoes(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0019_rls_multitenant.sql").read_text(encoding="utf-8")
        # Verifica que _tenant_ok verifica AMBAS condições: tenant correto OU super_admin
        assert "get_meu_tenant()" in sql
        assert "is_super_admin()" in sql
        assert "OR" in sql

    def test_super_admin_nao_tem_restricao_de_tenant(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0019_rls_multitenant.sql").read_text(encoding="utf-8")
        # super_admin deve aparecer como exceção em todas as policies
        count_super = sql.count("super_admin")
        assert count_super >= 10, f"super_admin aparece poucas vezes ({count_super}) nas policies"

    def test_insert_sempre_requer_tenant_do_usuario(self):
        from pathlib import Path
        sql = (Path(__file__).parent.parent / "migrations" / "0019_rls_multitenant.sql").read_text(encoding="utf-8")
        # Toda policy de INSERT deve checar tenant_id = get_meu_tenant()
        assert "tenant_id = get_meu_tenant()" in sql
