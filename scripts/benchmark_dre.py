"""
MX Seguros — DRE-IA
Benchmark EXPLAIN ANALYZE da função dre_por_periodo().

Uso:
    # Medir ANTES de aplicar 0010/0011:
    python scripts/benchmark_dre.py --label antes

    # Após aplicar as migrations:
    python scripts/benchmark_dre.py --label depois

    # Comparar dois resultados salvos:
    python scripts/benchmark_dre.py --comparar
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

RESULTS_DIR = Path(__file__).parent.parent / "benchmark_results"
RESULTS_DIR.mkdir(exist_ok=True)

# Converte postgresql+asyncpg:// → URL que asyncpg entende
_raw_url = os.environ.get("DATABASE_URL", "")
DATABASE_URL = _raw_url.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
# asyncpg.connect() aceita DSN no formato: user:pass@host:port/db
# ou como URL: postgresql://user:pass@host:port/db
DATABASE_DSN = "postgresql://" + DATABASE_URL if DATABASE_URL else None

# Períodos de teste — usa o último ano completo + trimestre atual
PERIODOS = [
    ("2025-01-01", "2025-03-31", "Q1 2025"),
    ("2025-01-01", "2025-12-31", "Ano 2025"),
    ("2026-01-01", "2026-03-31", "Q1 2026"),
]

EXPLAIN_QUERY = """
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT dre_por_periodo($1::date, $2::date)
"""


async def medir_periodo(conn: asyncpg.Connection, inicio: str, fim: str, label_periodo: str) -> dict:
    rows = await conn.fetch(EXPLAIN_QUERY, inicio, fim)
    plan = json.loads(rows[0][0])  # asyncpg retorna JSON como string

    node = plan[0]["Plan"]
    exec_ms = plan[0].get("Execution Time", 0)
    plan_ms = plan[0].get("Planning Time", 0)
    total_ms = exec_ms + plan_ms

    shared_hit    = node.get("Shared Hit Blocks", 0)
    shared_read   = node.get("Shared Read Blocks", 0)
    seq_scans     = _contar_seq_scans(node)

    return {
        "periodo": label_periodo,
        "planning_ms": round(plan_ms, 2),
        "execution_ms": round(exec_ms, 2),
        "total_ms": round(total_ms, 2),
        "shared_hit_blocks": shared_hit,
        "shared_read_blocks": shared_read,
        "seq_scans": seq_scans,
        "raw_plan": plan,
    }


def _contar_seq_scans(node: dict) -> int:
    count = 1 if node.get("Node Type") == "Seq Scan" else 0
    for child in node.get("Plans", []):
        count += _contar_seq_scans(child)
    return count


async def executar(label: str) -> None:
    if not DATABASE_DSN:
        print("[ERRO] DATABASE_URL não encontrada no .env")
        print("       Rode as queries manualmente no Supabase SQL Editor.")
        _imprimir_sql_manual()
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"  BENCHMARK dre_por_periodo() — {label.upper()}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")

    try:
        conn = await asyncpg.connect(DATABASE_DSN, timeout=15)
    except Exception as e:
        print(f"[ERRO] Falha ao conectar: {e}")
        print()
        print("  Alternativa: rode o SQL abaixo no Supabase SQL Editor")
        _imprimir_sql_manual()
        sys.exit(1)

    resultados = []
    for inicio, fim, nome in PERIODOS:
        try:
            r = await medir_periodo(conn, inicio, fim, nome)
            resultados.append(r)
            seq_label = "⚠ SEQ SCANS" if r["seq_scans"] > 0 else "✓ INDEX SCANS"
            print(f"\n  [{nome}]")
            print(f"    Planning:  {r['planning_ms']:>8.2f} ms")
            print(f"    Execution: {r['execution_ms']:>8.2f} ms")
            print(f"    Total:     {r['total_ms']:>8.2f} ms   {seq_label} ({r['seq_scans']} seq)")
            print(f"    Buffers:   hit={r['shared_hit_blocks']}  read={r['shared_read_blocks']}")
        except Exception as e:
            print(f"  [{nome}] ERRO: {e}")

    await conn.close()

    # Salva resultado para comparação futura
    out_file = RESULTS_DIR / f"benchmark_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(resultados, indent=2, default=str), encoding="utf-8")
    print(f"\n  Resultado salvo em: {out_file.name}")
    print(f"{'=' * 60}\n")


def comparar() -> None:
    arquivos = sorted(RESULTS_DIR.glob("benchmark_*.json"))
    if len(arquivos) < 2:
        print("[AVISO] Precisa de pelo menos 2 arquivos de benchmark para comparar.")
        return

    antes_file  = arquivos[0]
    depois_file = arquivos[-1]
    antes  = json.loads(antes_file.read_text())
    depois = json.loads(depois_file.read_text())

    print(f"\n{'=' * 70}")
    print("  COMPARAÇÃO: ANTES vs DEPOIS dos índices compostos + views")
    print(f"  Antes:  {antes_file.name}")
    print(f"  Depois: {depois_file.name}")
    print(f"{'=' * 70}")
    print(f"  {'Período':<20} {'Antes (ms)':>12} {'Depois (ms)':>12} {'Ganho':>10}  Seq scans")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*10}  ----------")

    for a, d in zip(antes, depois):
        ganho_pct = ((a["total_ms"] - d["total_ms"]) / max(a["total_ms"], 0.01)) * 100
        seq_a = a["seq_scans"]
        seq_d = d["seq_scans"]
        sinal = "▼" if ganho_pct > 0 else "▲"
        print(
            f"  {a['periodo']:<20} {a['total_ms']:>12.2f} {d['total_ms']:>12.2f}"
            f" {sinal}{abs(ganho_pct):>8.1f}%  {seq_a}→{seq_d}"
        )

    print(f"{'=' * 70}\n")


def _imprimir_sql_manual() -> None:
    print()
    print("  SQL para rodar no Supabase SQL Editor")
    print()
    print("  EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)")
    print("  SELECT dre_por_periodo('2025-01-01'::date, '2025-12-31'::date);")
    print()
    print("  Rode ANTES de aplicar migration 0010 e guarde o output.")
    print("  Rode DEPOIS e compare o 'Execution Time' e 'Seq Scan' vs")
    print("  'Index Scan' em comissoes, estornos, repasses e despesas.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark dre_por_periodo()")
    parser.add_argument("--label",    default="teste", help="Nome do snapshot (antes/depois)")
    parser.add_argument("--comparar", action="store_true", help="Compara snapshots salvos")
    args = parser.parse_args()

    if args.comparar:
        comparar()
    else:
        asyncio.run(executar(args.label))


if __name__ == "__main__":
    main()
