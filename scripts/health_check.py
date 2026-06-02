#!/usr/bin/env python3
"""
MX Seguros — DRE-IA | Script de health check.

Verifica:
1. Conexão com Supabase (anon + service_role)
2. Tabelas existentes no banco
3. RLS ativo nas tabelas sensíveis
4. Endpoint /health do backend
5. Anthropic API (sem cobrar tokens — apenas valida a chave)

Execute:
    python scripts/health_check.py
    python scripts/health_check.py --backend-url https://seu-backend.com
"""
from __future__ import annotations

import argparse
import sys
import os

# Adiciona raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK  = "[OK]"
ERR = "[ERRO]"
SKIP = "[SKIP]"


def check(label: str, fn):
    try:
        fn()
        print(f"  {OK}  {label}")
        return True
    except Exception as e:
        print(f"  {ERR} {label}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-url", default="http://localhost:8000")
    args = parser.parse_args()

    falhas = 0
    print("\n===========================================")
    print("   MX Seguros - DRE-IA | Health Check")
    print("===========================================\n")

    # ── 1. Config / .env ─────────────────────────────────────────
    print("1. Configuracao (.env)")
    from app.config import cfg

    def _check_supabase_url():
        assert cfg.supabase_url.startswith("https://"), "URL inválida"
    def _check_anon_key():
        assert cfg.supabase_anon_key.startswith("sb_"), "Anon key inválida"
    def _check_service_key():
        assert cfg.supabase_service_role_key.startswith("sb_"), "Service role key inválida"
    def _check_anthropic():
        assert cfg.anthropic_api_key, "ANTHROPIC_API_KEY não definida"

    for label, fn in [
        ("SUPABASE_URL",              _check_supabase_url),
        ("SUPABASE_ANON_KEY",         _check_anon_key),
        ("SUPABASE_SERVICE_ROLE_KEY", _check_service_key),
        ("ANTHROPIC_API_KEY",         _check_anthropic),
    ]:
        if not check(label, fn):
            falhas += 1

    # ── 2. Conexão Supabase ──────────────────────────────────────
    print("\n2. Conexao Supabase")
    from app.database import get_supabase_admin

    def _tabelas_existem():
        admin = get_supabase_admin()
        # Tenta ler uma linha de cada tabela crítica
        for tabela in ["usuarios", "comissoes", "repasses", "despesas", "audit_log"]:
            admin.table(tabela).select("id").limit(1).execute()

    if not check("Tabelas criticas acessiveis", _tabelas_existem):
        falhas += 1

    # ── 3. RLS ativo ─────────────────────────────────────────────
    print("\n3. Row-Level Security")
    from supabase import create_client
    from app.config import cfg as c

    def _rls_bloqueia_anonimo():
        # Cliente anônimo NÃO deve ver dados de usuarios
        anon = create_client(c.supabase_url, c.supabase_anon_key)
        resp = anon.table("usuarios").select("id").execute()
        # RLS deve retornar 0 linhas (não exceção) ou lançar 401
        assert len(resp.data) == 0, \
            f"RLS falhou: anon conseguiu ler {len(resp.data)} usuários!"

    if not check("Anonimo nao le 'usuarios'", _rls_bloqueia_anonimo):
        falhas += 1

    # ── 4. Backend HTTP ──────────────────────────────────────────
    print(f"\n4. Backend ({args.backend_url})")
    try:
        import httpx

        def _health():
            try:
                r = httpx.get(f"{args.backend_url}/health", timeout=5)
                assert r.status_code == 200, f"status {r.status_code}"
                assert r.json()["status"] == "ok"
            except httpx.ConnectError:
                raise AssertionError("Backend nao esta rodando (inicie com: uvicorn app.main:app --reload)")

        def _chat_sem_token():
            try:
                r = httpx.post(f"{args.backend_url}/chat",
                               json={"pergunta": "teste"},
                               timeout=5)
                assert r.status_code == 401, f"Esperava 401, recebeu {r.status_code}"
            except httpx.ConnectError:
                raise AssertionError("Backend nao esta rodando")

        if not check("GET /health", _health): falhas += 1
        if not check("POST /chat sem token -> 401", _chat_sem_token): falhas += 1
    except ImportError:
        print(f"  {SKIP} httpx nao instalado - pule: pip install httpx")

    # ── 5. Tools de IA ──────────────────────────────────────────
    print("\n5. Camada de IA")
    from app.ai.tools import tools_para_perfil, PERMISSOES_TOOL

    def _permissoes_ok():
        comercial = {t["name"] for t in tools_para_perfil("comercial")}
        assert "comparar_periodos" not in comercial
        assert "analisar_receita_por_ramo" not in comercial
        assert "consultar_dre" in comercial

    if not check("Matriz de permissoes de tools", _permissoes_ok): falhas += 1

    from app.ai.prompts.system import montar_system_prompt

    def _prompt_nao_vaza_chave():
        p = montar_system_prompt("uid", "admin", None, None, "2026-05")
        assert cfg.supabase_service_role_key not in p

    if not check("System prompt nao vaza service_role_key", _prompt_nao_vaza_chave): falhas += 1

    # ── Resumo ───────────────────────────────────────────────────
    print("\n===========================================")
    if falhas == 0:
        print(f"  {OK}  Todos os checks passaram!\n")
    else:
        print(f"  {ERR} {falhas} check(s) falharam.\n")
    print("===========================================\n")

    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
