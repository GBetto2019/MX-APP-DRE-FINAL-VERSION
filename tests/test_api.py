"""
MX Seguros — DRE-IA | Testes de integração da API (Fase 3).

Testa os 4 perfis em cada endpoint, validando:
- Autenticação (401 sem token)
- Autorização (403 para perfis sem permissão)
- Resposta correta (200 com dados filtrados)

Execute:
    pytest tests/test_api.py -v

Pré-requisito:
    python tests/setup_usuarios_teste.py
"""
from __future__ import annotations

import os
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from supabase import create_client

from app.main import app

load_dotenv()
load_dotenv(".env.test", override=False)

SUPABASE_URL     = os.environ["SUPABASE_URL"]
SUPABASE_ANON    = os.environ["SUPABASE_ANON_KEY"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

CREDENCIAIS = {
    "admin":     ("admin@mxseguros.test",     "Teste@123"),
    "gestor":    ("gestor@mxseguros.test",    "Teste@123"),
    "comercial": ("comercial@mxseguros.test", "Teste@123"),
    "contador":  ("contador@mxseguros.test",  "Teste@123"),
}

PERIODO = {"inicio": "2026-01-01", "fim": "2026-12-31"}
COMPETENCIA = {"competencia": "2026-01-01"}


# ── FIXTURES ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="session")
def tokens() -> dict[str, str]:
    """JWT de cada perfil via login no Supabase."""
    resultado: dict[str, str] = {}
    for role, (email, senha) in CREDENCIAIS.items():
        anon = create_client(SUPABASE_URL, SUPABASE_ANON)
        resp = anon.auth.sign_in_with_password({"email": email, "password": senha})
        assert resp.session, f"Login falhou para {role}"
        resultado[role] = resp.session.access_token
    return resultado


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── HEALTH ────────────────────────────────────────────────────

class TestHealth:

    def test_health_sem_auth(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("ok", "healthy", "degraded")


# ── AUTENTICAÇÃO ──────────────────────────────────────────────

class TestAutenticacao:

    def test_dre_sem_token_retorna_401(self, client):
        resp = client.get("/dre", params=PERIODO)
        assert resp.status_code == 401

    def test_comissoes_sem_token_retorna_401(self, client):
        resp = client.get("/comissoes", params=PERIODO)
        assert resp.status_code == 401

    def test_estornos_sem_token_retorna_401(self, client):
        resp = client.get("/estornos", params=PERIODO)
        assert resp.status_code == 401

    def test_metas_sem_token_retorna_401(self, client):
        resp = client.get("/metas", params=COMPETENCIA)
        assert resp.status_code == 401

    def test_repasses_sem_token_retorna_401(self, client):
        resp = client.get("/repasses", params=PERIODO)
        assert resp.status_code == 401

    def test_token_invalido_retorna_401(self, client):
        resp = client.get("/dre", params=PERIODO, headers={"Authorization": "Bearer token_falso"})
        assert resp.status_code == 401


# ── DRE ───────────────────────────────────────────────────────

class TestEndpointDRE:

    def test_admin_acessa_dre(self, client, tokens):
        resp = client.get("/dre", params=PERIODO, headers=headers(tokens["admin"]))
        assert resp.status_code == 200
        dados = resp.json()
        assert "dre" in dados
        assert "ebitda" in dados["dre"]
        assert "receita_bruta" in dados["dre"]
        assert dados["perfil"] == "admin"

    def test_gestor_acessa_dre_sem_ebitda(self, client, tokens):
        resp = client.get("/dre", params=PERIODO, headers=headers(tokens["gestor"]))
        assert resp.status_code == 200
        dados = resp.json()
        dre = dados["dre"]
        assert "receita_bruta" in dre
        # Gestor não deve ver EBITDA nem despesas fixas
        assert dre.get("ebitda") is None or dre.get("ebitda") == 0
        assert dre.get("despesas_fixas") is None or dre.get("despesas_fixas") == 0

    def test_comercial_acessa_dre(self, client, tokens):
        resp = client.get("/dre", params=PERIODO, headers=headers(tokens["comercial"]))
        assert resp.status_code == 200
        assert resp.json()["perfil"] == "comercial"

    def test_contador_acessa_dre_completo(self, client, tokens):
        resp = client.get("/dre", params=PERIODO, headers=headers(tokens["contador"]))
        assert resp.status_code == 200
        assert "ebitda" in resp.json()["dre"]

    def test_dre_periodo_invalido(self, client, tokens):
        """fim antes de inicio deve retornar 422."""
        resp = client.get(
            "/dre",
            params={"inicio": "2026-12-01", "fim": "2026-01-01"},
            headers=headers(tokens["admin"]),
        )
        assert resp.status_code == 422

    def test_ramos_bloqueado_para_comercial(self, client, tokens):
        resp = client.get("/dre/ramos", params=PERIODO, headers=headers(tokens["comercial"]))
        assert resp.status_code == 403

    def test_ramos_disponivel_para_admin(self, client, tokens):
        resp = client.get("/dre/ramos", params=PERIODO, headers=headers(tokens["admin"]))
        assert resp.status_code == 200
        assert "items" in resp.json()


# ── COMISSÕES ─────────────────────────────────────────────────

class TestEndpointComissoes:

    def test_admin_acessa_comissoes(self, client, tokens):
        resp = client.get("/comissoes", params=PERIODO, headers=headers(tokens["admin"]))
        assert resp.status_code == 200
        assert "items" in resp.json()
        assert "soma_total" in resp.json()

    def test_comercial_acessa_proprias_comissoes(self, client, tokens):
        resp = client.get("/comissoes", params=PERIODO, headers=headers(tokens["comercial"]))
        assert resp.status_code == 200

    def test_gestor_acessa_comissoes_equipe(self, client, tokens):
        resp = client.get("/comissoes", params=PERIODO, headers=headers(tokens["gestor"]))
        assert resp.status_code == 200

    def test_contador_acessa_todas_comissoes(self, client, tokens):
        resp = client.get("/comissoes", params=PERIODO, headers=headers(tokens["contador"]))
        assert resp.status_code == 200


# ── ESTORNOS ──────────────────────────────────────────────────

class TestEndpointEstornos:

    def test_admin_acessa_estornos(self, client, tokens):
        resp = client.get("/estornos", params=PERIODO, headers=headers(tokens["admin"]))
        assert resp.status_code == 200
        dados = resp.json()
        assert "taxa_estorno" in dados
        assert "alerta_5pct" in dados

    def test_todos_perfis_acessam_estornos(self, client, tokens):
        for role in ["admin", "gestor", "comercial", "contador"]:
            resp = client.get("/estornos", params=PERIODO, headers=headers(tokens[role]))
            assert resp.status_code == 200, f"Falhou para {role}: {resp.text}"


# ── METAS ─────────────────────────────────────────────────────

class TestEndpointMetas:

    def test_admin_acessa_metas(self, client, tokens):
        resp = client.get("/metas", params=COMPETENCIA, headers=headers(tokens["admin"]))
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_todos_perfis_acessam_metas(self, client, tokens):
        for role in ["admin", "gestor", "comercial", "contador"]:
            resp = client.get("/metas", params=COMPETENCIA, headers=headers(tokens[role]))
            assert resp.status_code == 200, f"Falhou para {role}: {resp.text}"


# ── REPASSES ──────────────────────────────────────────────────

class TestEndpointRepasses:

    def test_admin_acessa_repasses(self, client, tokens):
        resp = client.get("/repasses", params=PERIODO, headers=headers(tokens["admin"]))
        assert resp.status_code == 200
        dados = resp.json()
        assert "soma_previsto" in dados
        assert "soma_pago" in dados

    def test_todos_perfis_acessam_repasses(self, client, tokens):
        for role in ["admin", "gestor", "comercial", "contador"]:
            resp = client.get("/repasses", params=PERIODO, headers=headers(tokens[role]))
            assert resp.status_code == 200, f"Falhou para {role}: {resp.text}"
