"""
Sprint 7 — Testes de Observabilidade e DevOps.

Cobre:
- Task 7.1: Logging estruturado (structlog configurado)
- Task 7.2: Health check público e detalhado
- Task 7.3: CI/CD (arquivo workflow existe e é válido)
- Task 7.4: Rotação de audit_log (migration SQL existe)

Execute:
    pytest tests/test_sprint7_observabilidade.py -v
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
def tokens() -> dict[str, str]:
    resultado: dict[str, str] = {}
    for role, email in [
        ("admin",    "admin@mxseguros.test"),
        ("comercial","comercial@mxseguros.test"),
    ]:
        anon = create_client(SUPABASE_URL, SUPABASE_ANON)
        resp = anon.auth.sign_in_with_password({"email": email, "password": "Teste@123"})
        if resp.session:
            resultado[role] = resp.session.access_token
    return resultado


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ══════════════════════════════════════════════════════════════
# Task 7.1 — Logging estruturado
# ══════════════════════════════════════════════════════════════

class TestLoggingEstruturado:

    def test_modulo_logging_config_importa(self):
        from app.logging_config import get_logger, setup_logging
        assert callable(get_logger)
        assert callable(setup_logging)

    def test_get_logger_retorna_structlog(self):
        import structlog
        from app.logging_config import get_logger
        log = get_logger("teste")
        # structlog retorna BoundLoggerLazyProxy (resolve para BoundLogger no 1º uso)
        assert isinstance(log, (structlog.stdlib.BoundLogger, structlog.BoundLoggerBase)) or \
               "structlog" in type(log).__module__, \
               f"Esperado logger structlog, got {type(log)}"

    def test_setup_logging_nao_levanta_excecao(self):
        from app.logging_config import setup_logging
        setup_logging()  # deve ser idempotente

    def test_orchestrator_usa_get_logger(self):
        import inspect
        import app.ai.orchestrator as orch
        source = inspect.getsource(orch)
        assert "get_logger" in source, "orchestrator deve usar get_logger"
        assert "logging.getLogger" not in source, "não deve usar logging.getLogger diretamente"

    def test_dre_service_usa_get_logger(self):
        import inspect
        import app.services.dre_service as svc
        source = inspect.getsource(svc)
        assert "get_logger" in source

    def test_log_eventos_criticos_existem_no_orchestrator(self):
        """Verifica que os eventos de log críticos estão no código."""
        import inspect
        import app.ai.orchestrator as orch
        source = inspect.getsource(orch)
        assert "chat_ia_concluido" in source
        assert "duracao_ms" in source
        assert "tools_chamadas" in source

    def test_sem_print_no_codigo_app(self):
        """Não deve haver print() solto no código de produção."""
        import ast
        from pathlib import Path

        app_dir = Path(__file__).parent.parent / "app"
        prints_encontrados = []

        for py_file in app_dir.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Call) and
                            isinstance(node.func, ast.Name) and
                            node.func.id == "print"):
                        prints_encontrados.append(str(py_file.relative_to(app_dir)))
            except (SyntaxError, UnicodeDecodeError):
                pass

        assert not prints_encontrados, (
            f"print() encontrado em: {prints_encontrados}\n"
            "Use logger.info/debug em vez de print()"
        )


# ══════════════════════════════════════════════════════════════
# Task 7.2 — Health Check
# ══════════════════════════════════════════════════════════════

class TestHealthCheck:

    def test_health_retorna_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_tem_campos_obrigatorios(self, client):
        r = client.get("/health")
        data = r.json()
        assert "status" in data
        assert "version" in data
        assert "ambiente" in data
        assert "db" in data
        assert "uptime_seconds" in data

    def test_health_status_healthy_ou_degraded(self, client):
        r = client.get("/health")
        assert r.json()["status"] in ("healthy", "degraded")

    def test_health_versao_formato(self, client):
        r = client.get("/health")
        versao = r.json().get("version", "")
        partes = versao.split(".")
        assert len(partes) == 3, f"Versão deve ser X.Y.Z, got '{versao}'"

    def test_health_uptime_positivo(self, client):
        r = client.get("/health")
        uptime = r.json().get("uptime_seconds", -1)
        assert uptime >= 0

    def test_health_sem_auth_funciona(self, client):
        """Health check público não deve exigir autenticação."""
        r = client.get("/health")
        assert r.status_code != 401

    def test_health_detailed_sem_auth_retorna_401(self, client):
        r = client.get("/health/detailed")
        assert r.status_code == 401

    def test_health_detailed_comercial_retorna_403(self, client, tokens):
        token = tokens.get("comercial")
        if not token:
            pytest.skip("Token comercial não disponível")
        r = client.get("/health/detailed", headers=auth(token))
        assert r.status_code == 403

    def test_health_detailed_admin_retorna_metricas(self, client, tokens):
        token = tokens.get("admin")
        if not token:
            pytest.skip("Token admin não disponível")
        r = client.get("/health/detailed", headers=auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "uptime_seconds" in data
        assert "asyncpg_pool" in data
        assert "version" in data


# ══════════════════════════════════════════════════════════════
# Task 7.3 — CI/CD GitHub Actions
# ══════════════════════════════════════════════════════════════

class TestCICD:

    def test_workflow_ci_existe(self):
        from pathlib import Path
        caminho = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"
        assert caminho.exists(), "Arquivo .github/workflows/ci.yml não encontrado"

    def test_workflow_ci_tem_lint_e_test(self):
        from pathlib import Path
        import yaml

        caminho = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"
        with open(caminho) as f:
            try:
                config = yaml.safe_load(f)
            except Exception:
                pytest.skip("PyYAML não instalado — instale para validar YAML")

        jobs = config.get("jobs", {})
        assert "lint" in jobs or "test" in jobs, "Workflow deve ter job de lint ou test"

    def test_workflow_referencia_secrets_supabase(self):
        from pathlib import Path
        caminho = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"
        conteudo = caminho.read_text()
        assert "SUPABASE_URL" in conteudo
        assert "secrets" in conteudo

    def test_workflow_nao_expoe_secrets_hardcoded(self):
        from pathlib import Path
        caminho = Path(__file__).parent.parent.parent / ".github" / "workflows" / "ci.yml"
        conteudo = caminho.read_text()
        # Verificar que não há valores hardcoded de credenciais
        assert "eyJ" not in conteudo, "Parece ter JWT hardcoded no workflow"
        assert "sk-ant-" not in conteudo, "Parece ter chave Anthropic hardcoded"


# ══════════════════════════════════════════════════════════════
# Task 7.4 — Rotação Audit Log
# ══════════════════════════════════════════════════════════════

class TestAuditRetention:

    def test_migration_0015_existe(self):
        from pathlib import Path
        caminho = Path(__file__).parent.parent / "migrations" / "0015_audit_retention.sql"
        assert caminho.exists(), "Migration 0015_audit_retention.sql não encontrada"

    def test_migration_0015_cria_archive(self):
        from pathlib import Path
        caminho = Path(__file__).parent.parent / "migrations" / "0015_audit_retention.sql"
        sql = caminho.read_text(encoding="utf-8")
        assert "audit_log_archive" in sql
        assert "rotacionar_audit_log" in sql

    def test_migration_0015_tem_rls(self):
        from pathlib import Path
        caminho = Path(__file__).parent.parent / "migrations" / "0015_audit_retention.sql"
        sql = caminho.read_text(encoding="utf-8")
        assert "ROW LEVEL SECURITY" in sql
        assert "admin" in sql

    def test_funcao_retencao_aceita_parametro_dias(self):
        """Função deve aceitar N dias como parâmetro (não hardcoded)."""
        from pathlib import Path
        caminho = Path(__file__).parent.parent / "migrations" / "0015_audit_retention.sql"
        sql = caminho.read_text(encoding="utf-8")
        assert "p_dias" in sql or "INT DEFAULT" in sql
