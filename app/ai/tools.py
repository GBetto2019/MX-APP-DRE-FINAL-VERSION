"""
MX Seguros — DRE-IA | Definição e execução das tools da IA (§5.2).

SEGURANÇA:
- Toda chamada de tool valida SE o perfil pode chamar aquela tool.
- O LLM NUNCA recebe SQL, credenciais ou dados além do retorno da tool.
- Limite: 20 iterações de tool_use por mensagem.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from supabase import Client

from app.auth import UsuarioAtual

logger = logging.getLogger(__name__)

# ── DEFINIÇÕES DAS TOOLS (enviadas ao LLM) ────────────────────

TOOLS_DEFINICAO: list[dict] = [
    {
        "name": "consultar_dre",
        "description": (
            "Retorna o DRE (Demonstração do Resultado do Exercício) "
            "para o período informado. Dados já filtrados pelo perfil do usuário."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {"type": "string", "description": "Data início YYYY-MM-DD"},
                "fim":    {"type": "string", "description": "Data fim YYYY-MM-DD"},
            },
            "required": ["inicio", "fim"],
        },
    },
    {
        "name": "comparar_periodos",
        "description": "Compara DRE entre dois períodos (YoY ou MoM).",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo1_inicio": {"type": "string"},
                "periodo1_fim":    {"type": "string"},
                "periodo2_inicio": {"type": "string"},
                "periodo2_fim":    {"type": "string"},
            },
            "required": ["periodo1_inicio", "periodo1_fim", "periodo2_inicio", "periodo2_fim"],
        },
    },
    {
        "name": "analisar_receita_por_ramo",
        "description": "Detalha receita bruta por ramo de seguro no período.",
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {"type": "string"},
                "fim":    {"type": "string"},
            },
            "required": ["inicio", "fim"],
        },
    },
    {
        "name": "analisar_estornos",
        "description": "Analisa estornos do período com taxa e alerta de 5%.",
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {"type": "string"},
                "fim":    {"type": "string"},
            },
            "required": ["inicio", "fim"],
        },
    },
    {
        "name": "consultar_comissoes_produtor",
        "description": (
            "Retorna comissões agrupadas por produtor no período. "
            "Comercial só vê as próprias."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio":      {"type": "string"},
                "fim":         {"type": "string"},
                "produtor_id": {"type": "string", "description": "UUID do produtor (opcional)"},
            },
            "required": ["inicio", "fim"],
        },
    },
    {
        "name": "consultar_metas",
        "description": "Retorna metas e percentual de atingimento para o mês.",
        "input_schema": {
            "type": "object",
            "properties": {
                "competencia": {"type": "string", "description": "Mês YYYY-MM-DD"},
            },
            "required": ["competencia"],
        },
    },
    {
        "name": "consultar_repasses",
        "description": "Lista repasses previstos e pagos a produtores no período.",
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio":      {"type": "string"},
                "fim":         {"type": "string"},
                "produtor_id": {"type": "string", "description": "UUID do produtor (opcional)"},
            },
            "required": ["inicio", "fim"],
        },
    },
]

# ── MATRIZ DE PERMISSÃO POR TOOL (§5.2) ───────────────────────

PERMISSOES_TOOL: dict[str, set[str]] = {
    "consultar_dre":              {"admin", "gestor", "comercial", "contador"},
    "comparar_periodos":          {"admin", "gestor", "contador"},
    "analisar_receita_por_ramo":  {"admin", "gestor", "contador"},
    "analisar_estornos":          {"admin", "gestor", "comercial", "contador"},
    "consultar_comissoes_produtor": {"admin", "gestor", "comercial", "contador"},
    "consultar_metas":            {"admin", "gestor", "comercial", "contador"},
    "consultar_repasses":         {"admin", "gestor", "comercial", "contador"},
}


def tools_para_perfil(role: str) -> list[dict]:
    """Retorna apenas as tools que o perfil pode chamar."""
    return [
        t for t in TOOLS_DEFINICAO
        if role in PERMISSOES_TOOL.get(t["name"], set())
    ]


# ── EXECUTOR DE TOOLS ─────────────────────────────────────────

async def executar_tool(
    nome:    str,
    inputs:  dict[str, Any],
    usuario: UsuarioAtual,
    db:      Client,
) -> dict[str, Any]:
    """
    Executa uma tool validando a permissão do usuário.
    TODA chamada revalida o perfil — não confia no LLM.
    """
    roles_permitidos = PERMISSOES_TOOL.get(nome, set())
    if usuario.role not in roles_permitidos:
        logger.warning(
            "Tool %s negada para role %s (user_id=%s)",
            nome, usuario.role, usuario.user_id,
        )
        return {"erro": f"Ferramenta '{nome}' não disponível para seu perfil."}

    try:
        return await _dispatch(nome, inputs, usuario, db)
    except Exception as e:
        logger.error("Erro ao executar tool %s: %s", nome, e)
        return {"erro": f"Erro ao consultar dados: {str(e)}"}


async def _dispatch(
    nome:    str,
    inputs:  dict[str, Any],
    usuario: UsuarioAtual,
    db:      Client,
) -> dict[str, Any]:
    """Despacha para a função correta conforme o nome da tool."""
    from app.services import dre_service

    if nome == "consultar_dre":
        resultado = await dre_service.buscar_dre(
            date.fromisoformat(inputs["inicio"]),
            date.fromisoformat(inputs["fim"]),
            usuario, db,
        )
        return resultado.model_dump(mode="json")

    if nome == "comparar_periodos":
        dre1 = await dre_service.buscar_dre(
            date.fromisoformat(inputs["periodo1_inicio"]),
            date.fromisoformat(inputs["periodo1_fim"]),
            usuario, db,
        )
        dre2 = await dre_service.buscar_dre(
            date.fromisoformat(inputs["periodo2_inicio"]),
            date.fromisoformat(inputs["periodo2_fim"]),
            usuario, db,
        )
        return {"periodo1": dre1.model_dump(mode="json"), "periodo2": dre2.model_dump(mode="json")}

    if nome == "analisar_receita_por_ramo":
        resultado = await dre_service.buscar_receita_por_ramo(
            date.fromisoformat(inputs["inicio"]),
            date.fromisoformat(inputs["fim"]),
            db,
        )
        return resultado.model_dump(mode="json")

    if nome == "analisar_estornos":
        resultado = await dre_service.buscar_estornos(
            date.fromisoformat(inputs["inicio"]),
            date.fromisoformat(inputs["fim"]),
            usuario, db,
        )
        return resultado.model_dump(mode="json")

    if nome == "consultar_comissoes_produtor":
        # Comercial só pode ver as próprias
        produtor_id = inputs.get("produtor_id")
        if usuario.role == "comercial":
            produtor_id = usuario.produtor_id

        resultado = await dre_service.buscar_comissoes(
            date.fromisoformat(inputs["inicio"]),
            date.fromisoformat(inputs["fim"]),
            usuario, db,
        )
        return resultado.model_dump(mode="json")

    if nome == "consultar_metas":
        resultado = await dre_service.buscar_metas(
            date.fromisoformat(inputs["competencia"]),
            usuario, db,
        )
        return resultado.model_dump(mode="json")

    if nome == "consultar_repasses":
        produtor_id = inputs.get("produtor_id")
        if usuario.role == "comercial":
            produtor_id = usuario.produtor_id

        resultado = await dre_service.buscar_repasses(
            date.fromisoformat(inputs["inicio"]),
            date.fromisoformat(inputs["fim"]),
            usuario, db,
            produtor_id=produtor_id,
        )
        return resultado.model_dump(mode="json")

    return {"erro": f"Tool '{nome}' não implementada."}
