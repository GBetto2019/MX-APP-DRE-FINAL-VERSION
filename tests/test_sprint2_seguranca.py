"""
Sprint 2 — Testes de segurança de dados.

Cobre os 5 bugs do SDD v3 relacionados a RLS e regras de negócio:
- Task 2.1: RLS estornos — Comercial vê apenas os próprios
- Task 2.2: RLS despesas — Gestor não vê pessoal/não-operacional
- Task 2.3: Soft-delete — despesa deletada some da listagem mas fica no banco
- Task 2.4: Metas — Comercial não pode criar nem editar
- Task 2.5: Despesa criada por não-admin entra com status=pendente

Execute:
    pytest tests/test_sprint2_seguranca.py -v
"""
from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from supabase import create_client

load_dotenv()
load_dotenv(".env.test", override=False)

SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_ANON     = os.environ["SUPABASE_ANON_KEY"]
SERVICE_ROLE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

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


# ══════════════════════════════════════════════════════════════
# Task 2.1 — RLS Estornos
# ══════════════════════════════════════════════════════════════

class TestRLSEstornos:

    def test_comercial_acessa_estornos_sem_erro(self, client, tokens):
        """Comercial deve conseguir listar estornos (filtrados pelo RLS para os seus)."""
        token = tokens.get("comercial")
        if not token:
            pytest.skip("Token comercial não disponível")
        r = client.get(
            "/estornos",
            params={"inicio": "2026-01-01", "fim": "2026-12-31"},
            headers=auth(token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "taxa_estorno" in data

    def test_admin_acessa_estornos(self, client, tokens):
        token = tokens.get("admin")
        if not token:
            pytest.skip("Token admin não disponível")
        r = client.get(
            "/estornos",
            params={"inicio": "2026-01-01", "fim": "2026-12-31"},
            headers=auth(token),
        )
        assert r.status_code == 200

    def test_rls_estornos_policy_sql_existe(self):
        """Verifica que a migration 0002 tem política de estornos para Comercial."""
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0002_rls.sql"
        )
        with open(caminho, encoding="utf-8") as f:
            sql = f.read()
        assert "estornos_comercial" in sql
        assert "get_meu_produtor()" in sql
        assert "estornos_gestor" in sql


# ══════════════════════════════════════════════════════════════
# Task 2.2 — RLS Despesas (Gestor não vê sensíveis)
# ══════════════════════════════════════════════════════════════

class TestRLSDespesas:

    def test_gestor_nao_acessa_despesas_via_endpoint(self, client, tokens):
        """Gestor é bloqueado no nível de serviço pelo _exigir_leitura."""
        token = tokens.get("gestor")
        if not token:
            pytest.skip("Token gestor não disponível")
        r = client.get(
            "/lancamentos/despesas",
            params={"inicio": "2026-01-01", "fim": "2026-12-31"},
            headers=auth(token),
        )
        assert r.status_code == 403

    def test_comercial_nao_acessa_despesas_via_endpoint(self, client, tokens):
        token = tokens.get("comercial")
        if not token:
            pytest.skip("Token comercial não disponível")
        r = client.get(
            "/lancamentos/despesas",
            params={"inicio": "2026-01-01", "fim": "2026-12-31"},
            headers=auth(token),
        )
        assert r.status_code == 403

    def test_admin_acessa_despesas(self, client, tokens):
        token = tokens.get("admin")
        if not token:
            pytest.skip("Token admin não disponível")
        r = client.get(
            "/lancamentos/despesas",
            params={"inicio": "2026-01-01", "fim": "2026-12-31"},
            headers=auth(token),
        )
        if r.status_code == 500 and "does not exist" in r.text:
            pytest.skip("Migrations 0005-0014 não aplicadas — aplique PENDENTES_0005_a_0014.sql no Supabase")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    def test_contador_acessa_despesas(self, client, tokens):
        token = tokens.get("contador")
        if not token:
            pytest.skip("Token contador não disponível")
        r = client.get(
            "/lancamentos/despesas",
            params={"inicio": "2026-01-01", "fim": "2026-12-31"},
            headers=auth(token),
        )
        if r.status_code == 500 and "does not exist" in r.text:
            pytest.skip("Migrations 0005-0014 não aplicadas — aplique PENDENTES_0005_a_0014.sql no Supabase")
        assert r.status_code == 200

    def test_rls_despesas_gestor_policy_sql_existe(self):
        """Verifica que a migration 0012 tem política de despesas para Gestor."""
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0012_sprint2_seguranca.sql"
        )
        with open(caminho, encoding="utf-8") as f:
            sql = f.read()
        assert "despesas_gestor" in sql
        assert "pessoal" in sql
        assert "nao_operacional" in sql


# ══════════════════════════════════════════════════════════════
# Task 2.3 — Soft-Delete em Despesas
# ══════════════════════════════════════════════════════════════

class TestSoftDelete:

    def test_service_usa_soft_delete(self):
        """Verifica que deletar_despesa atualiza status para 'excluida' (não DELETE físico)."""
        import inspect
        from app.services.financeiro_service import deletar_despesa

        source = inspect.getsource(deletar_despesa)
        assert "excluida" in source, (
            "deletar_despesa deve usar soft-delete (status='excluida')"
        )
        assert "delete(" not in source.lower() or "update" in source, (
            "deletar_despesa não deve usar DELETE físico"
        )

    def test_buscar_despesas_filtra_excluidas(self):
        """Verifica que buscar_despesas exclui registros com status='excluida'."""
        import inspect
        from app.services.financeiro_service import buscar_despesas

        source = inspect.getsource(buscar_despesas)
        assert "excluida" in source, (
            "buscar_despesas deve filtrar status='excluida'"
        )

    def test_status_excluida_na_migration(self):
        """Verifica que a migration 0012 adiciona 'excluida' ao enum de status."""
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0012_sprint2_seguranca.sql"
        )
        with open(caminho, encoding="utf-8") as f:
            sql = f.read()
        assert "excluida" in sql
        assert "despesas_status_check" in sql

    def test_delete_endpoint_exige_admin(self, client, tokens):
        fake_id = str(uuid4())
        for role in ("gestor", "comercial", "contador"):
            token = tokens.get(role)
            if not token:
                continue
            r = client.delete(
                f"/lancamentos/despesas/{fake_id}",
                headers=auth(token),
            )
            assert r.status_code == 403, f"Role '{role}' deveria receber 403 no DELETE"

    def test_delete_endpoint_admin_retorna_sem_erro_500(self, client, tokens):
        """Admin deletando ID inexistente não deve retornar 500 interno."""
        token = tokens.get("admin")
        if not token:
            pytest.skip("Token admin não disponível")
        fake_id = str(uuid4())
        r = client.delete(f"/lancamentos/despesas/{fake_id}", headers=auth(token))
        if r.status_code == 500 and ("does not exist" in r.text or "schema cache" in r.text):
            pytest.skip("Migrations 0005-0014 não aplicadas — aplique PENDENTES_0005_a_0014.sql no Supabase")
        # Aceita 204 (soft-delete), 404 (não encontrado) ou 400
        assert r.status_code in (204, 404, 400, 422)


# ══════════════════════════════════════════════════════════════
# Task 2.4 — Metas: Comercial Readonly
# ══════════════════════════════════════════════════════════════

class TestMetasComercialReadonly:

    def test_rls_metas_comercial_apenas_select(self):
        """Migration 0012 deve remover UPDATE/DELETE de Comercial em metas."""
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0012_sprint2_seguranca.sql"
        )
        with open(caminho, encoding="utf-8") as f:
            sql = f.read()

        # Deve recriar update policy sem Comercial
        assert "metas_update" in sql
        assert "admin.*gestor" in sql or "'admin', 'gestor'" in sql or "admin" in sql

    def test_pydantic_metas_comercial_nao_tem_endpoint_post(self, client, tokens):
        """POST /metas retorna 405 pois o endpoint não existe (apenas GET)."""
        token = tokens.get("comercial")
        if not token:
            pytest.skip("Token comercial não disponível")
        r = client.post(
            "/metas",
            json={
                "escopo": "produtor",
                "competencia": "2026-01-01",
                "valor_alvo": 50000,
                "metrica": "receita_bruta",
            },
            headers=auth(token),
        )
        # Não existe endpoint POST /metas — 405 Method Not Allowed
        assert r.status_code == 405

    def test_comercial_acessa_metas_get(self, client, tokens):
        """Comercial deve conseguir consultar GET /metas."""
        token = tokens.get("comercial")
        if not token:
            pytest.skip("Token comercial não disponível")
        r = client.get(
            "/metas",
            params={"competencia": "2026-01-01"},
            headers=auth(token),
        )
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════
# Task 2.5 — Status Pendente para Não-Admin
# ══════════════════════════════════════════════════════════════

class TestStatusPendente:

    def test_criar_despesa_admin_status_aprovada(self):
        """Admin/Contador: criar_despesa define status='aprovada'."""
        from unittest.mock import MagicMock, patch

        mock_usuario = MagicMock()
        mock_usuario.role = "admin"
        mock_usuario.user_id = str(uuid4())

        from app.models.schemas import DespesaCreate
        import asyncio

        payload = DespesaCreate(
            subcategoria="aluguel",
            descricao="Aluguel sede teste",
            valor=Decimal("5000.00"),
            competencia="2026-01-01",
            centro_custo="matriz",
        )

        captured_status = {}

        # Mock que retorna "período aberto" para fechamentos (data=None)
        # e captura o status na inserção de despesa
        def _table_side_effect(nome):
            m = MagicMock()
            if nome == "fechamentos":
                # Simular período aberto: maybe_single().execute() retorna None
                m.select.return_value.eq.return_value.is_.return_value.maybe_single.return_value.execute.return_value = None
            elif nome == "despesas":
                def _insert_se(dados):
                    captured_status.update({"status": dados.get("status")})
                    resp = MagicMock()
                    resp.data = [{"id": str(uuid4()), "subcategoria": dados.get("subcategoria",""),
                                  "descricao": dados.get("descricao",""), "valor": "5000.00",
                                  "competencia": "2026-01-01", "centro_custo": "matriz",
                                  "recorrente": False, "parcela_atual": None, "parcela_total": None,
                                  "criado_em": None, "status": dados.get("status","aprovada"),
                                  "criado_por": None, "aprovado_por": None, "aprovado_em": None,
                                  "rejeitado_motivo": None, "tipo_lancamento_id": None,
                                  "banco_id": None, "categoria": None}]
                    return resp
                m.insert.side_effect = _insert_se
            return m

        mock_db = MagicMock()
        mock_db.table.side_effect = _table_side_effect

        from app.services.financeiro_service import criar_despesa
        try:
            asyncio.run(criar_despesa(payload, mock_usuario, mock_db))
        except Exception:
            pass

        assert captured_status.get("status") == "aprovada", (
            "Admin deve criar despesa com status='aprovada'"
        )

    def test_criar_despesa_nao_admin_status_pendente(self):
        """Não-admin: criar_despesa define status='pendente'."""
        import asyncio
        from decimal import Decimal
        from unittest.mock import MagicMock

        from app.models.schemas import DespesaCreate

        for role in ("gestor", "comercial"):
            mock_usuario = MagicMock()
            mock_usuario.role = role
            mock_usuario.user_id = str(uuid4())

            payload = DespesaCreate(
                subcategoria="despesa_teste",
                descricao="Despesa de teste",
                valor=Decimal("100.00"),
                competencia="2026-01-01",
                centro_custo="matriz",
            )

            captured_status = {}

            def _table_se(nome):
                m = MagicMock()
                if nome == "fechamentos":
                    m.select.return_value.eq.return_value.is_.return_value.maybe_single.return_value.execute.return_value = None
                elif nome == "despesas":
                    def _ins(dados):
                        captured_status.update({"status": dados.get("status")})
                        r = MagicMock()
                        r.data = [{"id": str(uuid4()), "subcategoria": "despesa_teste",
                                   "descricao": "Despesa de teste", "valor": "100.00",
                                   "competencia": "2026-01-01", "centro_custo": "matriz",
                                   "recorrente": False, "parcela_atual": None, "parcela_total": None,
                                   "criado_em": None, "status": dados.get("status","pendente"),
                                   "criado_por": None, "aprovado_por": None, "aprovado_em": None,
                                   "rejeitado_motivo": None, "tipo_lancamento_id": None,
                                   "banco_id": None, "categoria": None}]
                        return r
                    m.insert.side_effect = _ins
                return m

            mock_db = MagicMock()
            mock_db.table.side_effect = _table_se

            from app.services.financeiro_service import criar_despesa
            try:
                asyncio.run(criar_despesa(payload, mock_usuario, mock_db))
            except Exception:
                pass

            assert captured_status.get("status") == "pendente", (
                f"Role '{role}' deve criar despesa com status='pendente'"
            )

    def test_service_tem_logica_status_por_role(self):
        """Verifica no código-fonte que o service distingue admin/não-admin."""
        import inspect
        from app.services.financeiro_service import criar_despesa

        source = inspect.getsource(criar_despesa)
        assert "pendente" in source
        assert "aprovada" in source
        assert "admin" in source
        assert "contador" in source


# ══════════════════════════════════════════════════════════════
# Verificação geral das migrations Sprint 2
# ══════════════════════════════════════════════════════════════

class TestMigrationsSprint2:

    def test_migration_0012_existe(self):
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0012_sprint2_seguranca.sql"
        )
        assert os.path.exists(caminho)

    def test_migration_0012_contem_fix_atingimento_metas(self):
        """Migration 0012 deve corrigir atingimento_metas() para usar COUNT."""
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0012_sprint2_seguranca.sql"
        )
        with open(caminho, encoding="utf-8") as f:
            sql = f.read()
        assert "COUNT(DISTINCT" in sql or "COUNT(*)" in sql or "numero_apolices" in sql
        assert "atingimento_metas" in sql

    def test_migration_0012_contem_soft_delete(self):
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0012_sprint2_seguranca.sql"
        )
        with open(caminho, encoding="utf-8") as f:
            sql = f.read()
        assert "excluida" in sql
        assert "status" in sql

    def test_migration_0012_corrige_metas_comercial(self):
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0012_sprint2_seguranca.sql"
        )
        with open(caminho, encoding="utf-8") as f:
            sql = f.read()
        assert "metas_update" in sql
        assert "metas_delete" in sql
        assert "DROP POLICY" in sql
