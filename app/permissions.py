"""
MX Seguros — DRE-IA | Permissões granulares por tela e ação.

Estrutura: {"tela": {"acao": bool}}
Telas: visao_geral, dre, lancamentos, aprovacoes, assistente, configuracoes
"""
from __future__ import annotations

DEFAULT_PERMISSIONS: dict[str, dict] = {
    "admin": {
        "visao_geral":   {"visualizar": True},
        "dre":           {"visualizar": True},
        "lancamentos":   {"visualizar": True, "criar": True, "editar": True, "deletar": True},
        "aprovacoes":    {"visualizar": True, "aprovar": True},
        "assistente":    {"visualizar": True},
        "configuracoes": {"visualizar": True, "criar": True, "editar": True},
    },
    "gestor": {
        "visao_geral":   {"visualizar": True},
        "dre":           {"visualizar": True},
        "lancamentos":   {"visualizar": True, "criar": True, "editar": True, "deletar": False},
        "aprovacoes":    {"visualizar": True, "aprovar": True},
        "assistente":    {"visualizar": True},
        "configuracoes": {"visualizar": True, "criar": True, "editar": True},
    },
    "comercial": {
        "visao_geral":   {"visualizar": True},
        "dre":           {"visualizar": True},
        "lancamentos":   {"visualizar": True, "criar": True, "editar": False, "deletar": False},
        "aprovacoes":    {"visualizar": False, "aprovar": False},
        "assistente":    {"visualizar": True},
        "configuracoes": {"visualizar": True, "criar": False, "editar": False},
    },
    "contador": {
        "visao_geral":   {"visualizar": True},
        "dre":           {"visualizar": True},
        "lancamentos":   {"visualizar": True, "criar": True, "editar": False, "deletar": False},
        "aprovacoes":    {"visualizar": False, "aprovar": False},
        "assistente":    {"visualizar": True},
        "configuracoes": {"visualizar": True, "criar": False, "editar": False},
    },
}


def get_default_permissions(role: str) -> dict:
    return DEFAULT_PERMISSIONS.get(role, DEFAULT_PERMISSIONS["comercial"])


def resolver_permissions(role: str, permissions_db: dict | None) -> dict:
    """Retorna permissions_db se definido, senão as permissões padrão da role."""
    if permissions_db is None:
        return get_default_permissions(role)
    return permissions_db


def tem_permissao(permissions: dict, tela: str, acao: str) -> bool:
    return bool(permissions.get(tela, {}).get(acao, False))
