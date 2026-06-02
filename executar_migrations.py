"""
MX Seguros — DRE-IA
Executa as migrations SQL diretamente no Supabase.

Uso:
    python executar_migrations.py                     # usa Management API (requer PAT)
    python executar_migrations.py --apenas 0005       # roda só a migration 0005
    python executar_migrations.py --apenas PENDENTES  # roda PENDENTES_0005_a_0014.sql
    python executar_migrations.py --reset             # cuidado: dropa tudo e recria

Para usar a Management API, adicione ao .env:
    SUPABASE_ACCESS_TOKEN=sbp_... (crie em https://supabase.com/dashboard/account/tokens)

Alternativa: aplique manualmente no SQL Editor:
    https://supabase.com/dashboard/project/jrqmntvmtukmhlmnukgn/sql/new
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL      = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ACCESS_TOKEN      = os.environ.get("SUPABASE_ACCESS_TOKEN", "")   # PAT opcional
PROJ_REF          = SUPABASE_URL.replace("https://", "").split(".")[0]
MIGRATIONS_DIR    = Path(__file__).parent / "migrations"

HEADERS_REST = {
    "apikey":        SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}


def executar_sql(sql: str, descricao: str) -> bool:
    """Executa SQL via Management API (PAT) ou asyncpg (DATABASE_URL)."""
    # 1) Tentar Management API com PAT
    if ACCESS_TOKEN:
        ok = _via_management_api(sql, descricao)
        if ok:
            return True

    # 2) Tentar asyncpg direto (requer DATABASE_URL com senha correta e porta 5432 aberta)
    ok = _via_asyncpg(sql, descricao)
    if ok:
        return True

    # 3) Fallback: RPC exec_sql (requer função criada manualmente)
    return _via_rpc_exec_sql(sql, descricao)


def _via_management_api(sql: str, descricao: str) -> bool:
    """Management API: requer SUPABASE_ACCESS_TOKEN (PAT)."""
    url = f"https://api.supabase.com/v1/projects/{PROJ_REF}/database/query"
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
            json={"query": sql},
            timeout=60,
        )
        if resp.status_code in (200, 201, 204):
            print(f"  [OK] {descricao}")
            return True
        return False
    except Exception:
        return False


def _via_asyncpg(sql: str, descricao: str) -> bool:
    """Conexão direta PostgreSQL via asyncpg (porta 5432)."""
    import asyncio
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url or "senha" in db_url:
        return False
    dsn = db_url.replace("postgresql+asyncpg://", "postgresql://")

    async def _run():
        import asyncpg
        conn = await asyncpg.connect(dsn, ssl="require", timeout=15)
        await conn.execute(sql)
        await conn.close()

    try:
        asyncio.run(_run())
        print(f"  [OK] {descricao}")
        return True
    except Exception:
        return False


def _via_rpc_exec_sql(sql: str, descricao: str) -> bool:
    """Fallback: RPC exec_sql (precisa existir no banco)."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    try:
        resp = httpx.post(url, json={"query": sql}, headers=HEADERS_REST, timeout=60)
        if resp.status_code in (200, 201, 204):
            print(f"  [OK] {descricao}")
            return True
    except Exception:
        pass

    print(f"  [ERRO] {descricao}")
    print(f"         Nenhum método de execução disponível.")
    print(f"         Aplique manualmente: https://supabase.com/dashboard/project/{PROJ_REF}/sql/new")
    return False


def rodar_arquivo(caminho: Path) -> bool:
    print(f"\n>>> Rodando: {caminho.name}")
    sql = caminho.read_text(encoding="utf-8")

    # Executa em blocos separados por "-- ──" para melhor diagnóstico
    ok = executar_sql(sql, caminho.name)
    return ok


def listar_migrations(apenas: str | None = None) -> list[Path]:
    arquivos = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if apenas:
        arquivos = [f for f in arquivos if f.name.startswith(apenas)]
    return arquivos


def main() -> None:
    parser = argparse.ArgumentParser(description="Executor de migrations MX DRE-IA")
    parser.add_argument("--apenas", help="Prefixo da migration (ex: 0001)")
    parser.add_argument("--reset",  action="store_true",
                        help="PERIGO: dropa todas as tabelas e recria do zero")
    args = parser.parse_args()

    print("=" * 55)
    print("  MX Seguros DRE-IA — Executor de Migrations")
    print("=" * 55)
    print(f"  Supabase: {SUPABASE_URL}")
    print()

    if args.reset:
        confirmar = input("ATENCAO: --reset vai APAGAR TODOS OS DADOS. Digite 'sim' para continuar: ")
        if confirmar.lower() != "sim":
            print("Abortado.")
            sys.exit(0)
        _resetar()

    migrations = listar_migrations(args.apenas)
    if not migrations:
        print("[AVISO] Nenhuma migration encontrada.")
        sys.exit(1)

    print(f"  {len(migrations)} migration(s) encontrada(s):\n")
    for m in migrations:
        print(f"   - {m.name}")

    print()
    erros = 0
    for migration in migrations:
        ok = rodar_arquivo(migration)
        if not ok:
            erros += 1

    print()
    print("=" * 55)
    if erros == 0:
        print(f"  [SUCESSO] {len(migrations)} migration(s) aplicada(s)!")
    else:
        print(f"  [ATENCAO] {erros} erro(s) encontrado(s).")
        print()
        print("  Se o erro for de autenticacao, rode as migrations")
        print("  diretamente no SQL Editor do Supabase:")
        print(f"  https://supabase.com/dashboard/project/"
              f"{SUPABASE_URL.replace('https://','').split('.')[0]}/sql/new")
        sys.exit(1)
    print("=" * 55)


def _resetar() -> None:
    drop_sql = """
    DROP TABLE IF EXISTS audit_log       CASCADE;
    DROP TABLE IF EXISTS metas           CASCADE;
    DROP TABLE IF EXISTS impostos        CASCADE;
    DROP TABLE IF EXISTS despesas        CASCADE;
    DROP TABLE IF EXISTS estornos        CASCADE;
    DROP TABLE IF EXISTS repasses        CASCADE;
    DROP TABLE IF EXISTS comissoes       CASCADE;
    DROP TABLE IF EXISTS apolices        CASCADE;
    DROP TABLE IF EXISTS clientes        CASCADE;
    DROP TABLE IF EXISTS ramos           CASCADE;
    DROP TABLE IF EXISTS seguradoras     CASCADE;
    DROP TABLE IF EXISTS usuarios        CASCADE;
    DROP TABLE IF EXISTS produtores      CASCADE;
    DROP TABLE IF EXISTS equipes         CASCADE;
    DROP TYPE  IF EXISTS despesa_categoria CASCADE;
    DROP TYPE  IF EXISTS user_role         CASCADE;
    DROP FUNCTION IF EXISTS get_meu_role()         CASCADE;
    DROP FUNCTION IF EXISTS get_minha_equipe()     CASCADE;
    DROP FUNCTION IF EXISTS get_meu_produtor()     CASCADE;
    DROP FUNCTION IF EXISTS dre_por_periodo(DATE, DATE)            CASCADE;
    DROP FUNCTION IF EXISTS receita_por_ramo(DATE, DATE)           CASCADE;
    DROP FUNCTION IF EXISTS taxa_estorno(DATE, DATE)               CASCADE;
    DROP FUNCTION IF EXISTS comissoes_por_produtor(DATE, DATE, UUID) CASCADE;
    DROP FUNCTION IF EXISTS atingimento_metas(DATE)                CASCADE;
    """
    executar_sql(drop_sql, "RESET: removendo schema anterior")


if __name__ == "__main__":
    main()
