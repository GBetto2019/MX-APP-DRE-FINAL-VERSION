"""
Sprint 0 — Testes de segurança e validação.

Cobre:
- Task 0.1: Rate limiting (limiter configurado e aplicado)
- Task 0.2: Security headers em todas as respostas
- Task 0.4: Validação de período máximo (365 dias)
- Task 0.5: Validação Pydantic (valores negativos, strings longas)

Execute:
    pytest tests/test_sprint0_seguranca.py -v

Nota: rate limiting real (429) exigiria muitas requisições simultâneas;
aqui verificamos configuração e que o middleware está registrado.
"""
from __future__ import annotations

import os

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
    resp = anon.auth.sign_in_with_password({
        "email": "admin@mxseguros.test",
        "password": "Teste@123",
    })
    assert resp.session, "Login admin falhou — rode setup_usuarios_teste.py"
    return resp.session.access_token


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ══════════════════════════════════════════════════════════════
# Task 0.1 — Rate Limiting (configuração)
# ══════════════════════════════════════════════════════════════

class TestRateLimiting:

    def test_limiter_registrado_no_app(self):
        """Verifica que o state do app tem o limiter configurado."""
        assert hasattr(app.state, "limiter"), "limiter não registrado em app.state"

    def test_limiter_aplicado_no_chat(self):
        """Verifica que o limiter está importado e usado no router de chat."""
        from app.routers import chat as chat_module
        assert hasattr(chat_module, "limiter"), (
            "limiter não importado em app/routers/chat.py"
        )

    def test_health_nao_tem_rate_limit(self, client):
        """Health check deve responder sem limitação."""
        for _ in range(5):
            r = client.get("/health")
            assert r.status_code == 200


# ══════════════════════════════════════════════════════════════
# Task 0.2 — Security Headers
# ══════════════════════════════════════════════════════════════

class TestSecurityHeaders:

    def test_x_content_type_options(self, client):
        r = client.get("/health")
        assert r.headers.get("x-content-type-options") == "nosniff", (
            "Header X-Content-Type-Options ausente"
        )

    def test_x_frame_options(self, client):
        r = client.get("/health")
        assert r.headers.get("x-frame-options") == "DENY", (
            "Header X-Frame-Options ausente"
        )

    def test_x_xss_protection(self, client):
        r = client.get("/health")
        assert r.headers.get("x-xss-protection") == "1; mode=block", (
            "Header X-XSS-Protection ausente"
        )

    def test_headers_em_endpoint_autenticado(self, client, token_admin):
        r = client.get(
            "/dre",
            params={"inicio": "2026-01-01", "fim": "2026-03-31"},
            headers=auth(token_admin),
        )
        # Mesmo em 401/403/200, os headers de segurança devem estar presentes
        assert "x-content-type-options" in r.headers
        assert "x-frame-options" in r.headers

    def test_cors_sem_origin_nao_bloqueia_health(self, client):
        """Sem header Origin (chamada server-to-server), health responde normalmente."""
        r = client.get("/health")
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════
# Task 0.4 — Validação de Período
# ══════════════════════════════════════════════════════════════

class TestValidacaoPeriodo:

    def test_periodo_maior_365_dias_retorna_400(self, client, token_admin):
        r = client.get(
            "/dre",
            params={"inicio": "2020-01-01", "fim": "2026-12-31"},
            headers=auth(token_admin),
        )
        assert r.status_code == 400
        assert "365" in r.json().get("detail", "") or "12 meses" in r.json().get("detail", "")

    def test_fim_antes_inicio_retorna_422(self, client, token_admin):
        r = client.get(
            "/dre",
            params={"inicio": "2026-06-01", "fim": "2026-01-01"},
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    def test_periodo_12_meses_exato_aceito(self, client, token_admin):
        r = client.get(
            "/dre",
            params={"inicio": "2026-01-01", "fim": "2026-12-31"},
            headers=auth(token_admin),
        )
        assert r.status_code != 400, "Período de 12 meses deve ser aceito"

    def test_periodo_invalido_em_comissoes(self, client, token_admin):
        r = client.get(
            "/comissoes",
            params={"inicio": "2020-01-01", "fim": "2026-12-31"},
            headers=auth(token_admin),
        )
        assert r.status_code == 400

    def test_periodo_invalido_em_estornos(self, client, token_admin):
        r = client.get(
            "/estornos",
            params={"inicio": "2020-01-01", "fim": "2026-12-31"},
            headers=auth(token_admin),
        )
        assert r.status_code == 400

    def test_periodo_invalido_em_repasses(self, client, token_admin):
        r = client.get(
            "/repasses",
            params={"inicio": "2020-01-01", "fim": "2026-12-31"},
            headers=auth(token_admin),
        )
        assert r.status_code == 400


# ══════════════════════════════════════════════════════════════
# Task 0.5 — Validação Pydantic
# ══════════════════════════════════════════════════════════════

class TestValidacaoPydantic:

    def test_despesa_valor_negativo_retorna_422(self, client, token_admin):
        r = client.post(
            "/lancamentos/despesas",
            json={
                "subcategoria": "aluguel",
                "descricao": "Aluguel sede",
                "valor": -100.00,
                "competencia": "2026-01-01",
                "centro_custo": "matriz",
            },
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    def test_despesa_valor_zero_aceito_pydantic(self, client, token_admin):
        """Valor zero deve passar na validação Pydantic (ge=0). Erros de negócio são OK."""
        r = client.post(
            "/lancamentos/despesas",
            json={
                "subcategoria": "ajuste",
                "descricao": "Ajuste zerado",
                "valor": 0,
                "competencia": "2026-01-01",
                "centro_custo": "matriz",
            },
            headers=auth(token_admin),
        )
        # Se for 422, deve ser por motivo diferente de "valor < 0"
        if r.status_code == 422:
            erros = r.json().get("detail", [])
            msgs = [str(e) for e in erros]
            assert not any("ge" in m or "greater" in m for m in msgs), (
                "Pydantic está rejeitando valor=0, mas ge=0 deveria permitir"
            )

    def test_despesa_descricao_vazia_retorna_422(self, client, token_admin):
        r = client.post(
            "/lancamentos/despesas",
            json={
                "subcategoria": "teste",
                "descricao": "ab",  # min_length=3
                "valor": 100.00,
                "competencia": "2026-01-01",
                "centro_custo": "matriz",
            },
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    def test_despesa_descricao_muito_longa_retorna_422(self, client, token_admin):
        r = client.post(
            "/lancamentos/despesas",
            json={
                "subcategoria": "teste",
                "descricao": "x" * 501,  # max_length=500
                "valor": 100.00,
                "competencia": "2026-01-01",
                "centro_custo": "matriz",
            },
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    def test_despesa_centro_custo_invalido_retorna_422(self, client, token_admin):
        r = client.post(
            "/lancamentos/despesas",
            json={
                "subcategoria": "aluguel",
                "descricao": "Aluguel filial",
                "valor": 500.00,
                "competencia": "2026-01-01",
                "centro_custo": "filial_xpto",  # inválido
            },
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    def test_despesa_competencia_futuro_distante_retorna_422(self, client, token_admin):
        r = client.post(
            "/lancamentos/despesas",
            json={
                "subcategoria": "aluguel",
                "descricao": "Aluguel futuro",
                "valor": 500.00,
                "competencia": "2030-01-01",  # muito no futuro
                "centro_custo": "matriz",
            },
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    def test_meta_escopo_invalido_retorna_422_pydantic(self):
        """MetaCreate com escopo inválido deve falhar na validação Pydantic."""
        from pydantic import ValidationError
        from app.models.schemas import MetaCreate
        from datetime import date

        with pytest.raises(ValidationError) as exc_info:
            MetaCreate(
                escopo="setor_invalido",
                competencia=date(2026, 1, 1),
                valor_alvo=50000,
                metrica="receita_bruta",
            )
        assert "escopo" in str(exc_info.value).lower()

    def test_meta_valor_negativo_retorna_422_pydantic(self):
        """MetaCreate com valor_alvo negativo deve falhar na validação Pydantic."""
        from pydantic import ValidationError
        from app.models.schemas import MetaCreate
        from datetime import date

        with pytest.raises(ValidationError) as exc_info:
            MetaCreate(
                escopo="global",
                competencia=date(2026, 1, 1),
                valor_alvo=-1000,
                metrica="receita_bruta",
            )
        assert "valor" in str(exc_info.value).lower() or "positive" in str(exc_info.value).lower()
