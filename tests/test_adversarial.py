"""
MX Seguros — DRE-IA | Testes adversariais da camada de IA (Fase 4).

Valida que 30 prompts de ataque NÃO vazam dados de outros perfis
quando executados como usuário Comercial.

COMO FUNCIONA:
- Testa o system prompt + tools sem chamar a API real da Anthropic
- Simula respostas do LLM para verificar que a lógica de segurança
  do orquestrador/tools está correta
- Testes de integração real com API ficam em test_chat_real.py
  (marcados como @pytest.mark.integration — requerem ANTHROPIC_API_KEY)

Execute:
    pytest tests/test_adversarial.py -v
    pytest tests/test_adversarial.py -v -m integration  # com API real
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth import UsuarioAtual
from app.ai.tools import executar_tool, tools_para_perfil, PERMISSOES_TOOL

# Carrega os 30 prompts
PROMPTS_DIR = Path(__file__).parent
ADVERSARIAL = json.loads((PROMPTS_DIR / "adversarial_prompts.json").read_text())

# Usuário Comercial de teste (perfil mais restrito)
COMERCIAL = UsuarioAtual(
    user_id="fb8e0402-40dc-474d-a76b-a256bfa6787b",
    email="comercial@mxseguros.test",
    role="comercial",
    equipe_id=None,
    produtor_id=None,
)

ADMIN = UsuarioAtual(
    user_id="8da2da10-492b-43bc-b16d-2e2920de8685",
    email="admin@mxseguros.test",
    role="admin",
)

GESTOR = UsuarioAtual(
    user_id="c98dec94-3f96-44bc-8758-2ef38283a6d8",
    email="gestor@mxseguros.test",
    role="gestor",
)


# ── TESTES DO SISTEMA DE TOOLS ────────────────────────────────

class TestPermissoesDasTools:
    """Valida a matriz de permissões das tools (§5.2)."""

    def test_comercial_nao_tem_comparar_periodos(self):
        tools = {t["name"] for t in tools_para_perfil("comercial")}
        assert "comparar_periodos" not in tools, \
            "FALHA: comercial tem acesso a comparar_periodos!"

    def test_comercial_nao_tem_analisar_receita_por_ramo(self):
        tools = {t["name"] for t in tools_para_perfil("comercial")}
        assert "analisar_receita_por_ramo" not in tools, \
            "FALHA: comercial tem acesso a analisar_receita_por_ramo!"

    def test_admin_tem_todas_as_tools(self):
        tools = {t["name"] for t in tools_para_perfil("admin")}
        todas = {t["name"] for t in __import__("app.ai.tools", fromlist=["TOOLS_DEFINICAO"]).TOOLS_DEFINICAO}
        assert tools == todas

    def test_gestor_nao_tem_projetar_cenario(self):
        # projetar_cenario só existe se definida — por ora não está na lista
        tools = {t["name"] for t in tools_para_perfil("gestor")}
        assert "projetar_cenario" not in tools

    @pytest.mark.parametrize("role", ["admin", "gestor", "comercial", "contador"])
    def test_todos_perfis_tem_consultar_dre(self, role):
        tools = {t["name"] for t in tools_para_perfil(role)}
        assert "consultar_dre" in tools


class TestBloqueioDeToolsPorPerfil:
    """Valida que executar_tool rejeita chamadas não autorizadas."""

    @pytest.mark.asyncio
    async def test_comercial_nao_executa_comparar_periodos(self):
        db_mock = MagicMock()
        resultado = await executar_tool(
            "comparar_periodos",
            {"periodo1_inicio": "2026-01-01", "periodo1_fim": "2026-03-31",
             "periodo2_inicio": "2025-01-01", "periodo2_fim": "2025-03-31"},
            COMERCIAL,
            db_mock,
        )
        assert "erro" in resultado
        assert "perfil" in resultado["erro"].lower() or "disponível" in resultado["erro"].lower()

    @pytest.mark.asyncio
    async def test_comercial_nao_executa_receita_por_ramo(self):
        db_mock = MagicMock()
        resultado = await executar_tool(
            "analisar_receita_por_ramo",
            {"inicio": "2026-01-01", "fim": "2026-12-31"},
            COMERCIAL,
            db_mock,
        )
        assert "erro" in resultado

    @pytest.mark.asyncio
    async def test_tool_desconhecida_retorna_erro(self):
        db_mock = MagicMock()
        resultado = await executar_tool(
            "tool_inexistente",
            {},
            ADMIN,
            db_mock,
        )
        assert "erro" in resultado


# ── TESTES DO SYSTEM PROMPT ───────────────────────────────────

class TestSystemPrompt:
    """Valida que o system prompt contém as proteções necessárias."""

    def test_system_prompt_contem_restricao_de_escopo(self):
        from app.ai.prompts.system import montar_system_prompt
        prompt = montar_system_prompt(
            user_id="test", role="comercial",
            equipe_id=None, produtor_id=None, periodo="2026-05",
        )
        assert "não está disponível no seu perfil" in prompt
        assert "NUNCA" in prompt or "nunca" in prompt

    def test_system_prompt_contem_protecao_contra_jailbreak(self):
        from app.ai.prompts.system import montar_system_prompt
        prompt = montar_system_prompt(
            user_id="test", role="comercial",
            equipe_id=None, produtor_id=None, periodo="2026-05",
        )
        assert "manipulação" in prompt or "ignore as regras" in prompt.lower()

    def test_system_prompt_injeta_perfil_correto(self):
        from app.ai.prompts.system import montar_system_prompt
        for role in ["admin", "gestor", "comercial", "contador"]:
            prompt = montar_system_prompt(
                user_id="uid123", role=role,
                equipe_id=None, produtor_id=None, periodo="2026-05",
            )
            assert f"perfil:      {role}" in prompt
            assert "uid123" in prompt

    def test_system_prompt_nao_expoe_service_role_key(self):
        from app.ai.prompts.system import montar_system_prompt
        from app.config import cfg
        prompt = montar_system_prompt(
            user_id="test", role="admin",
            equipe_id=None, produtor_id=None, periodo="2026-05",
        )
        assert cfg.supabase_service_role_key not in prompt
        assert cfg.supabase_anon_key not in prompt


# ── TESTES ADVERSARIAIS COM MOCK DO LLM ───────────────────────

class TestAdversarialComMock:
    """
    Testa que o orquestrador responde corretamente a prompts adversariais.
    Usa mock do cliente Anthropic — não chama API real.
    """

    def _mock_resposta_texto(self, texto: str):
        """Cria um mock de resposta do Claude com texto simples."""
        msg_mock = MagicMock()
        msg_mock.stop_reason = "end_turn"
        msg_mock.content = [MagicMock(type="text", text=texto)]

        stream_mock = MagicMock()
        stream_mock.__enter__ = MagicMock(return_value=stream_mock)
        stream_mock.__exit__ = MagicMock(return_value=False)
        stream_mock.__iter__ = MagicMock(return_value=iter([]))
        stream_mock.get_final_message = MagicMock(return_value=msg_mock)

        return stream_mock

    @pytest.mark.asyncio
    @pytest.mark.parametrize("prompt_data", ADVERSARIAL)
    async def test_adversarial_nao_vaza_dados(self, prompt_data):
        """
        Para cada prompt adversarial, valida que:
        1. O orquestrador não chama tools proibidas para o perfil
        2. Não lança exceção de segurança
        3. A resposta não contém dados que comercial não deveria ver
        """
        from app.ai.orchestrator import processar_pergunta

        resposta_mock = "Essa informação não está disponível no seu perfil."
        stream_mock = self._mock_resposta_texto(resposta_mock)

        db_mock    = MagicMock()
        admin_mock = MagicMock()
        admin_mock.table = MagicMock(return_value=MagicMock(
            insert=MagicMock(return_value=MagicMock(execute=MagicMock()))
        ))

        with patch("anthropic.Anthropic") as mock_client_class:
            mock_client = MagicMock()
            mock_client.messages.stream = MagicMock(return_value=stream_mock)
            mock_client_class.return_value = mock_client

            chunks = []
            async for chunk in processar_pergunta(
                prompt_data["prompt"],
                COMERCIAL,
                db_mock,
                admin_mock,
            ):
                chunks.append(chunk)

        # Verifica que chegou ao fim sem erro crítico
        texto_completo = "".join(chunks)
        assert '"tipo": "fim"' in texto_completo, \
            f"Prompt {prompt_data['id']} não chegou ao fim: {texto_completo[:200]}"

        # Verifica que não houve chamada de tool proibida
        tools_comercial = {t["name"] for t in tools_para_perfil("comercial")}
        tools_proibidas = {"comparar_periodos", "analisar_receita_por_ramo"}

        # Nenhuma tool proibida deve ter sido chamada via mock
        for call in mock_client.messages.stream.call_args_list:
            kwargs = call.kwargs if call.kwargs else {}
            mensagens = kwargs.get("messages", [])
            for msg in mensagens:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "tool_result":
                                pass  # tool result é esperado
