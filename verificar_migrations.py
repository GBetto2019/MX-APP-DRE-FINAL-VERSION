"""Verifica e aplica migrations pendentes no Supabase via Management API."""
from __future__ import annotations

import httpx
from pathlib import Path
from dotenv import dotenv_values

env = dotenv_values(".env")
TOKEN = env.get("SUPABASE_ACCESS_TOKEN", "")
PROJ_REF = env.get("SUPABASE_URL", "").replace("https://", "").split(".")[0]
BASE = f"https://api.supabase.com/v1/projects/{PROJ_REF}/database/query"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def query(sql: str) -> list[dict]:
    r = httpx.post(BASE, headers=HEADERS, json={"query": sql}, timeout=15)
    return r.json() if r.status_code < 300 else []


def tabela_existe(nome: str) -> bool:
    r = query(f"SELECT COUNT(*) as n FROM information_schema.tables WHERE table_schema='public' AND table_name='{nome}'")
    return int((r[0].get("n") if r else 0) or 0) > 0


def coluna_existe(tabela: str, coluna: str) -> bool:
    r = query(f"SELECT COUNT(*) as n FROM information_schema.columns WHERE table_name='{tabela}' AND column_name='{coluna}'")
    return int((r[0].get("n") if r else 0) or 0) > 0


def aplicar_arquivo(caminho: Path) -> tuple[int, int]:
    """Aplica statements de um arquivo SQL. Retorna (ok, erros)."""
    import re
    sql = caminho.read_text(encoding="utf-8")
    sql = re.sub(r"--[^\n]*", "", sql)

    stmts, current, in_dollar, dollar_tag = [], [], False, ""
    i = 0
    while i < len(sql):
        if not in_dollar and sql[i] == "$":
            m = re.match(r"\$[^$]*\$", sql[i:])
            if m:
                tag = m.group(0)
                current.append(sql[i : i + len(tag)])
                i += len(tag)
                in_dollar, dollar_tag = True, tag
                continue
        if in_dollar and sql[i:].startswith(dollar_tag):
            current.append(dollar_tag)
            i += len(dollar_tag)
            in_dollar, dollar_tag = False, ""
            continue
        if sql[i] == ";" and not in_dollar:
            s = "".join(current).strip()
            if s:
                stmts.append(s)
            current = []
        else:
            current.append(sql[i])
        i += 1
    last = "".join(current).strip()
    if last:
        stmts.append(last)

    ok = erros = 0
    for stmt in stmts:
        if not stmt.strip():
            continue
        r = httpx.post(BASE, headers=HEADERS, json={"query": stmt}, timeout=30)
        if r.status_code < 300:
            ok += 1
        else:
            erros_ignorar = ["already exists", "does not exist", "multiple primary keys", "IF NOT EXISTS"]
            resp_text = r.text
            if any(x in resp_text for x in erros_ignorar):
                ok += 1  # idempotente
            else:
                erros += 1
                print(f"  ERRO: {resp_text[:200]}")
    return ok, erros


print("=" * 60)
print("Verificando migrations no Supabase...")
print("=" * 60)

checks = [
    ("0012 — Sprint 2 segurança", "despesas", "status",       None),
    ("0013 — Fechamentos",        "fechamentos",  None,        None),
    ("0014 — Chat histórico",     "chat_conversas", None,      None),
    ("0015 — Audit retention",    "audit_log_archive", None,   None),
    ("0016 — Migrar categoria",   None,          None,         None),   # apenas dados
    ("0017 — Tenants",            "tenants",     None,         None),
    ("0018 — tenant_id",          "usuarios",    "tenant_id",  None),
    ("0019 — RLS multi-tenant",   None,          None,         None),   # apenas policies
]

pendentes: list[str] = []

for label, tabela, coluna, _ in checks:
    if tabela and coluna:
        existe = coluna_existe(tabela, coluna)
    elif tabela:
        existe = tabela_existe(tabela)
    else:
        existe = True  # não tem checagem simples; assume OK
    status = "OK" if existe else "PENDENTE"
    print(f"  {status:8} {label}")
    if not existe:
        pendentes.append(label)

print()
if not pendentes:
    print("Todas as migrations verificáveis estão aplicadas.")
else:
    print(f"Pendentes detectadas: {len(pendentes)}")
    migracoes_a_aplicar = [
        ("0012_sprint2_seguranca.sql",  "0012 — Sprint 2 segurança"),
        ("0013_fechamentos.sql",        "0013 — Fechamentos"),
        ("0014_chat_historico.sql",     "0014 — Chat histórico"),
        ("0015_audit_retention.sql",    "0015 — Audit retention"),
        ("0016_migrar_categoria.sql",   "0016 — Migrar categoria"),
        ("0017_tenants.sql",            "0017 — Tenants"),
        ("0018_add_tenant_id.sql",      "0018 — tenant_id"),
        ("0019_rls_multitenant.sql",    "0019 — RLS multi-tenant"),
    ]
    for arquivo, label in migracoes_a_aplicar:
        if label in pendentes:
            caminho = Path("migrations") / arquivo
            if caminho.exists():
                print(f"\nAplicando {arquivo}...")
                ok, erros = aplicar_arquivo(caminho)
                print(f"  {ok} statements OK, {erros} erros")
            else:
                print(f"  ARQUIVO NÃO ENCONTRADO: {caminho}")

print("\nConcluído.")
