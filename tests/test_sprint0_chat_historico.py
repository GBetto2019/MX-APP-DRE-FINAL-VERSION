"""
Sprint 0 — Task 0.7: Testes de persistência de histórico do chat.

Testa o serviço de chat_service (unitário) e os endpoints de listagem.
O POST /chat usa SSE e Claude API — só testamos estrutura, não a IA.

Execute:
    pytest tests/test_sprint0_chat_historico.py -v
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
    if not resp.session:
        pytest.skip("Login admin falhou — rode setup_usuarios_teste.py")
    return resp.session.access_token


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Testes de estrutura dos endpoints ─────────────────────────

class TestChatHistoricoEndpoints:

    def test_listar_conversas_sem_auth_retorna_401(self, client):
        r = client.get("/chat/conversas")
        assert r.status_code == 401

    def test_listar_conversas_admin_retorna_lista(self, client, token_admin):
        r = client.get("/chat/conversas", headers=auth(token_admin))
        if r.status_code == 500 and "schema cache" in r.text:
            pytest.skip("Migration 0014 não aplicada — execute no SQL Editor do Supabase")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_mensagens_conversa_inexistente_retorna_404(self, client, token_admin):
        from uuid import uuid4
        fake_id = str(uuid4())
        r = client.get(f"/chat/conversas/{fake_id}/mensagens", headers=auth(token_admin))
        if r.status_code == 500 and "schema cache" in r.text:
            pytest.skip("Migration 0014 não aplicada — execute no SQL Editor do Supabase")
        assert r.status_code == 404

    def test_chat_request_sem_mensagem_retorna_422(self, client, token_admin):
        r = client.post("/chat", json={"mensagem": ""}, headers=auth(token_admin))
        assert r.status_code == 422

    def test_chat_request_mensagem_longa_retorna_422(self, client, token_admin):
        r = client.post(
            "/chat",
            json={"mensagem": "x" * 2001},
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    def test_chat_aceita_conversa_id_uuid(self, client, token_admin):
        """POST /chat com conversa_id UUID inválido deve retornar 422."""
        r = client.post(
            "/chat",
            json={"mensagem": "Olá", "conversa_id": "nao-e-uuid"},
            headers=auth(token_admin),
        )
        assert r.status_code == 422

    def test_chat_sem_auth_retorna_401(self, client):
        r = client.post("/chat", json={"mensagem": "Olá"})
        assert r.status_code == 401


# ── Testes unitários do serviço ────────────────────────────────

class TestChatService:

    def test_modulo_importa_sem_erro(self):
        from app.services import chat_service
        assert hasattr(chat_service, "criar_ou_retomar_conversa")
        assert hasattr(chat_service, "carregar_historico")
        assert hasattr(chat_service, "salvar_mensagem")
        assert hasattr(chat_service, "listar_conversas")
        assert hasattr(chat_service, "atualizar_titulo")

    def test_migration_arquivo_existe(self):
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0014_chat_historico.sql"
        )
        assert os.path.exists(caminho), "Migration 0014_chat_historico.sql não encontrada"

    def test_migration_contem_tabelas_necessarias(self):
        import os
        caminho = os.path.join(
            os.path.dirname(__file__),
            "..", "migrations", "0014_chat_historico.sql"
        )
        with open(caminho, encoding="utf-8") as f:
            sql = f.read()
        assert "chat_conversas" in sql
        assert "chat_mensagens" in sql
        assert "ROW LEVEL SECURITY" in sql
        assert "auth.uid()" in sql

    def test_orchestrator_aceita_conversa_id(self):
        """Verifica que o orchestrator aceita o parâmetro conversa_id."""
        import inspect
        from app.ai.orchestrator import processar_pergunta
        sig = inspect.signature(processar_pergunta)
        assert "conversa_id" in sig.parameters, (
            "orchestrator.processar_pergunta deve aceitar conversa_id"
        )

    def test_chat_router_tem_endpoint_conversas(self):
        """Verifica que os endpoints de histórico estão registrados."""
        rotas = [r.path for r in app.routes]
        assert "/chat/conversas" in rotas, "GET /chat/conversas não registrado"
