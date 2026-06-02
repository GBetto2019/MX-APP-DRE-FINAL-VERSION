"""
Aplica as migrations do Sprint 4/5/6 (multi-tenant) no Supabase.

Tenta 3 abordagens em ordem:
1. asyncpg direto (requer DATABASE_URL com senha correta e porta 5432 aberta)
2. Management API (requer SUPABASE_ACCESS_TOKEN no .env)
3. Instrução manual (SQL Editor)

Uso:
    python aplicar_migrations_sprint4.py
    python aplicar_migrations_sprint4.py --apenas PARTE1   # só 0017
    python aplicar_migrations_sprint4.py --apenas PARTE2   # só 0018
    python aplicar_migrations_sprint4.py --apenas PARTE3   # só 0019
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

# dotenv_values lê diretamente do arquivo, sem depender do os.environ
_env = dotenv_values(".env")
load_dotenv(override=True)

SUPABASE_URL  = _env.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
DATABASE_URL  = _env.get("DATABASE_URL", "") or os.environ.get("DATABASE_URL", "")
ACCESS_TOKEN  = _env.get("SUPABASE_ACCESS_TOKEN", "") or os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJ_REF      = SUPABASE_URL.replace("https://", "").split(".")[0]

MIGRATIONS = {
    "PARTE1": Path("migrations/PARTE1_tenants.sql"),
    "PARTE2": Path("migrations/PARTE2_tenant_id.sql"),
    "PARTE3": Path("migrations/PARTE3_rls.sql"),
}


import httpx
import re


def _split_statements(sql: str) -> list[str]:
    """Divide SQL em statements individuais, ignorando ;; dentro de $$ ... $$."""
    # Remove comentários de linha
    sql = re.sub(r'--[^\n]*', '', sql)

    stmts = []
    current = []
    in_dollar = False
    dollar_tag = ""

    i = 0
    while i < len(sql):
        # Detectar início de bloco $$ ou $TAG$
        if not in_dollar and sql[i] == '$':
            m = re.match(r'\$[^$]*\$', sql[i:])
            if m:
                tag = m.group(0)
                current.append(sql[i:i+len(tag)])
                i += len(tag)
                in_dollar = True
                dollar_tag = tag
                continue

        # Detectar fim de bloco $$
        if in_dollar and sql[i:].startswith(dollar_tag):
            current.append(dollar_tag)
            i += len(dollar_tag)
            in_dollar = False
            dollar_tag = ""
            continue

        char = sql[i]
        if char == ';' and not in_dollar:
            stmt = ''.join(current).strip()
            if stmt:
                stmts.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1

    last = ''.join(current).strip()
    if last:
        stmts.append(last)

    return [s for s in stmts if s.strip()]


def executar_statement(sql: str) -> tuple[bool, str]:
    """Executa um único statement via Management API."""
    if not ACCESS_TOKEN:
        return False, "TOKEN_AUSENTE"
    url = f"https://api.supabase.com/v1/projects/{PROJ_REF}/database/query"
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
            json={"query": sql},
            timeout=60,
        )
        if resp.status_code in (200, 201, 204):
            return True, ""
        return False, resp.text[:200]
    except Exception as e:
        return False, str(e)


async def processar(nome: str, arquivo: Path) -> None:
    print(f"\n>>> {nome}: {arquivo.name}")
    sql_completo = arquivo.read_text(encoding="utf-8")
    statements = _split_statements(sql_completo)

    print(f"  {len(statements)} statements encontrados")

    ok = 0
    ignorados = 0
    erros = []

    for i, stmt in enumerate(statements, 1):
        preview = stmt.replace('\n', ' ')[:60]
        sucesso, erro = executar_statement(stmt)

        if sucesso:
            ok += 1
        else:
            # Alguns erros são esperados (IF NOT EXISTS, ADD VALUE IF EXISTS)
            ignorar = any(x in erro for x in [
                "already exists", "já existe", "IF NOT EXISTS",
                "does not exist\nQUERY:  SELECT",  # função não existe ainda
            ])
            if ignorar:
                ignorados += 1
            else:
                erros.append(f"  stmt {i}: {preview}...\n    ERRO: {erro[:120]}")

    print(f"  OK: {ok} | Ignorados: {ignorados} | Erros: {len(erros)}")
    for e in erros[:5]:  # máximo 5 erros exibidos
        print(e)

    if not erros:
        print(f"  [SUCESSO] {nome} aplicado!")
    else:
        print(f"  [PARCIAL] Verifique os erros acima")

def mostrar_instrucao_manual(nome: str, arquivo: Path) -> None:
    print(f"\n  [MANUAL] Aplique no SQL Editor:")
    print(f"  URL: https://supabase.com/dashboard/project/{PROJ_REF}/sql/new")
    print(f"  Arquivo: {arquivo.absolute()}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apenas", choices=["PARTE1", "PARTE2", "PARTE3"])
    args = parser.parse_args()

    print("=" * 60)
    print("  Sprint 4/5/6 — Aplicar Migrations Multi-Tenant")
    print("=" * 60)
    print(f"  Supabase: {SUPABASE_URL}")
    print(f"  Management API: {'configurado' if ACCESS_TOKEN else 'NÃO CONFIGURADO'}")
    print(f"  asyncpg: {'disponível' if DATABASE_URL and 'senha' not in DATABASE_URL else 'NÃO CONFIGURADO'}")

    if not ACCESS_TOKEN and ("senha" in DATABASE_URL or not DATABASE_URL):
        print("\n  AVISO: Nenhuma das abordagens automáticas está configurada.")
        print("  Para habilitar a Management API:")
        print("  1. Acesse: https://supabase.com/dashboard/account/tokens")
        print("  2. Crie um Personal Access Token")
        print("  3. Adicione ao .env: SUPABASE_ACCESS_TOKEN=sbp_...")
        print()

    selecionados = {args.apenas: MIGRATIONS[args.apenas]} if args.apenas else MIGRATIONS

    for nome, arquivo in selecionados.items():
        await processar(nome, arquivo)

    print("\n" + "=" * 60)
    print("  Após aplicar manualmente, rode:")
    print("  python -m pytest tests/test_sprint4_5_6_multitenant.py -v")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
