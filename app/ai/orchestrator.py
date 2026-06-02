"""
MX Seguros — DRE-IA | Orquestrador da camada de IA.

Loop de tool_use:
1. Recebe a pergunta do usuário
2. Monta system prompt com contexto injetado pelo backend
3. Chama Claude API com as tools disponíveis para o perfil
4. Se stop_reason == "tool_use": executa tool, valida permissão, volta para Claude
5. Repete até stop_reason == "end_turn" ou limite de 20 iterações
6. Registra tudo no audit_log

Streaming via Server-Sent Events: cada chunk de texto é enviado
ao cliente conforme chega da API.
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import date
from uuid import UUID

import anthropic
from supabase import Client

from app.ai.prompts.system import montar_system_prompt
from app.ai.tools import executar_tool, tools_para_perfil
from app.auth import UsuarioAtual
from app.config import cfg
from app.logging_config import get_logger
from app.services import chat_service

logger = get_logger(__name__)

MODELO = "claude-sonnet-4-5"
MAX_TOOL_ITERACOES = 20   # Limite duro — evita loop/exfiltração (§5.3)


async def processar_pergunta(
    pergunta:    str,
    usuario:     UsuarioAtual,
    db:          Client,
    db_admin:    Client,
    conversa_id: UUID | None = None,
) -> AsyncGenerator[str, None]:
    """
    Processa uma pergunta do usuário com streaming de resposta.
    Yielda chunks SSE no formato: "data: <json>\n\n"

    Tipos de evento SSE:
    - {"tipo": "texto",  "conteudo": "..."}   → chunk de texto do LLM
    - {"tipo": "tool",   "nome": "...", "status": "chamando|concluido"}
    - {"tipo": "erro",   "mensagem": "..."}
    - {"tipo": "fim"}
    """
    import time
    t_inicio = time.monotonic()

    cliente = anthropic.Anthropic(api_key=cfg.anthropic_api_key or _get_api_key())

    system_prompt = montar_system_prompt(
        user_id=usuario.user_id,
        role=usuario.role,
        equipe_id=usuario.equipe_id,
        produtor_id=usuario.produtor_id,
        periodo=date.today().strftime("%Y-%m"),
    )

    # Persistência de histórico (graceful: funciona sem migration 0014)
    conv_id: str | None = None
    historico: list[dict] = []
    try:
        conv_id = await chat_service.criar_ou_retomar_conversa(
            conversa_id, usuario.user_id, db_admin,
            tenant_id=getattr(usuario, "tenant_id", None),
        )
        historico = await chat_service.carregar_historico(conv_id, db_admin)
        yield _sse({"tipo": "conversa_id", "conversa_id": conv_id})
    except Exception as e:
        logger.warning("Histórico de chat indisponível (migration pendente?): %s", e)

    tools = tools_para_perfil(usuario.role)
    mensagens: list[dict] = historico + [{"role": "user", "content": pergunta}]
    tools_chamadas: list[str] = []
    resposta_final: str = ""
    iteracao = 0

    try:
        while iteracao < MAX_TOOL_ITERACOES:
            iteracao += 1

            # Chama Claude com streaming
            texto_acumulado = ""
            tool_uses: list[dict] = []

            with cliente.messages.stream(
                model=MODELO,
                max_tokens=4096,
                system=system_prompt,
                messages=mensagens,
                tools=tools if tools else anthropic.NOT_GIVEN,
            ) as stream:
                stop_reason = None

                for event in stream:
                    if hasattr(event, "type"):

                        # Chunk de texto → envia ao cliente
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                chunk = event.delta.text
                                texto_acumulado += chunk
                                resposta_final += chunk
                                yield _sse({"tipo": "texto", "conteudo": chunk})

                        # Tool sendo chamada
                        elif event.type == "content_block_start":
                            if hasattr(event.content_block, "type") and \
                               event.content_block.type == "tool_use":
                                nome_tool = event.content_block.name
                                tool_id   = event.content_block.id
                                tool_uses.append({
                                    "id":     tool_id,
                                    "nome":   nome_tool,
                                    "inputs": {},
                                })
                                yield _sse({"tipo": "tool", "nome": nome_tool, "status": "chamando"})

                        # Input da tool acumulado
                        elif event.type == "content_block_delta":
                            if hasattr(event.delta, "partial_json") and tool_uses:
                                tool_uses[-1]["inputs_raw"] = \
                                    tool_uses[-1].get("inputs_raw", "") + event.delta.partial_json

                        elif event.type == "message_stop":
                            stop_reason = stream.get_final_message().stop_reason

                # Captura stop_reason do stream finalizado
                final_msg = stream.get_final_message()
                stop_reason = final_msg.stop_reason

                # Extrai tool_uses do content completo
                for bloco in final_msg.content:
                    if bloco.type == "tool_use":
                        tool_uses_completo = {
                            "id":     bloco.id,
                            "nome":   bloco.name,
                            "inputs": bloco.input,
                        }
                        # Atualiza ou adiciona
                        existente = next((t for t in tool_uses if t["id"] == bloco.id), None)
                        if existente:
                            existente["inputs"] = bloco.input
                        else:
                            tool_uses.append(tool_uses_completo)

            # Adiciona resposta do assistente ao histórico
            mensagens.append({
                "role": "assistant",
                "content": final_msg.content,
            })

            if stop_reason == "end_turn" or stop_reason is None:
                break

            if stop_reason == "tool_use":
                # Executa cada tool solicitada
                tool_results = []
                for tool in tool_uses:
                    nome   = tool.get("nome", "")
                    inputs = tool.get("inputs", {})
                    tid    = tool.get("id", "")

                    tools_chamadas.append(nome)
                    resultado = await executar_tool(nome, inputs, usuario, db)

                    yield _sse({"tipo": "tool", "nome": nome, "status": "concluido"})

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tid,
                        "content":     json.dumps(resultado, default=str, ensure_ascii=False),
                    })

                mensagens.append({"role": "user", "content": tool_results})

        else:
            # Limite atingido
            yield _sse({"tipo": "erro", "mensagem": "Limite de iterações atingido."})

    except anthropic.AuthenticationError:
        logger.error("anthropic_auth_error", usuario_id=usuario.user_id)
        yield _sse({"tipo": "erro", "mensagem": "Chave da API de IA não configurada."})
    except Exception as e:
        logger.error("orchestrator_erro", usuario_id=usuario.user_id, exc=str(e), exc_info=True)
        yield _sse({"tipo": "erro", "mensagem": "Erro interno ao processar sua pergunta."})
    else:
        # Salva mensagens no histórico (silencioso se tabelas não existirem)
        if conv_id:
            await chat_service.salvar_mensagem(conv_id, "user", pergunta, None, db_admin)
            if resposta_final:
                await chat_service.salvar_mensagem(
                    conv_id, "assistant", resposta_final, tools_chamadas or None, db_admin
                )
                titulo = pergunta[:80].strip()
                await chat_service.atualizar_titulo(conv_id, titulo, db_admin)
    finally:
        duracao_ms = int((time.monotonic() - t_inicio) * 1000)
        logger.info(
            "chat_ia_concluido",
            usuario_id=usuario.user_id,
            role=usuario.role,
            tools_chamadas=tools_chamadas,
            iteracoes=iteracao,
            duracao_ms=duracao_ms,
            resposta_chars=len(resposta_final),
        )
        await _registrar_log(
            usuario=usuario,
            pergunta=pergunta,
            tools_chamadas=tools_chamadas,
            resposta=resposta_final[:2000],
            db_admin=db_admin,
        )
        yield _sse({"tipo": "fim"})


def _sse(dados: dict) -> str:
    """Formata um evento SSE."""
    return f"data: {json.dumps(dados, ensure_ascii=False)}\n\n"


def _get_api_key() -> str:
    """Lê ANTHROPIC_API_KEY do ambiente."""
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY não definida no .env")
    return key


async def _registrar_log(
    usuario:       UsuarioAtual,
    pergunta:      str,
    tools_chamadas: list[str],
    resposta:      str,
    db_admin:      Client,
) -> None:
    """Registra a interação no audit_log (append-only)."""
    try:
        db_admin.table("audit_log").insert({
            "usuario_id": usuario.user_id,
            "acao":       "chat_ia",
            "detalhes": {
                "pergunta":       pergunta[:500],    # trunca para não logar dados sensíveis
                "tools_chamadas": tools_chamadas,
                "resposta_chars": len(resposta),
                "modelo":         MODELO,
            },
        }).execute()
    except Exception as e:
        logger.error("Falha ao registrar audit_log de chat: %s", e)
