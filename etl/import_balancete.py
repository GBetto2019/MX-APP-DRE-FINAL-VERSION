"""
MX Seguros — DRE-IA | Fase 2: ETL
Importa o Balancete 2026 (Itaú) para o banco de dados.

Uso:
    python etl/import_balancete.py
    python etl/import_balancete.py --dry-run   # mostra o que seria importado sem gravar
    python etl/import_balancete.py --arquivo "caminho/arquivo.xlsx"

Saídas:
    data/output/lancamentos_importados.csv   — tudo que foi importado
    data/output/revisar.csv                  — linhas sem classificação ou sem valor
    etl/MIGRACAO_2026.md                     — relatório completo da migração
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# Adiciona raiz ao path para importar categorizacao
sys.path.insert(0, str(Path(__file__).parent.parent))
from etl.categorizacao import classificar, SEGURADORAS

load_dotenv()

SUPABASE_URL      = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ARQUIVO_PADRAO    = Path(__file__).parent.parent / "Docs" / "Balancete 2026 (Itau).xlsx"
OUTPUT_DIR        = Path(__file__).parent.parent / "data" / "output"

# ── Estrutura de um lançamento parseado ───────────────────────

@dataclass
class Lancamento:
    data_pag:    date | None
    descricao:   str
    valor:       float | None     # None = não preenchido na planilha
    secao:       str              # gastos_fixos | gastos_variaveis | aguas_lindoia | agro | investimentos | recebimentos
    aba:         str
    linha_excel: int
    categoria:   str = ""
    subcategoria: str = ""
    tipo:        str = ""         # despesa | receita | imposto | investimento | revisar
    centro_custo: str = "matriz"
    seguradora_nome: str = ""
    motivo_revisar: str = ""


# ── PARSER DA PLANILHA ────────────────────────────────────────

def detectar_secao(val_col0: str, val_col1: str, secao_atual: str) -> str:
    """Detecta mudança de seção com base no cabeçalho da linha."""
    v0 = str(val_col0).lower().strip()
    v1 = str(val_col1).lower().strip()
    combinado = v0 + " " + v1

    if "recebimento" in v0 or "companhias de seguro" in v1:
        return "recebimentos"
    if "custo aguas" in v0 or "custo águas" in v0:
        return "aguas_lindoia"
    if "agronegocio" in v1 or "agronegócio" in v1:
        return "agro"
    if "investimentos prolongados" in v1:
        return "investimentos"
    if "gastos variav" in v0 or "gastos variáv" in v0:
        return "gastos_variaveis"
    if "gastos fixos" in v1 or ("data pag" in v0 and secao_atual == ""):
        return "gastos_fixos"
    return secao_atual


def e_linha_header_ou_total(val_col0: str, val_col1: str) -> bool:
    """Retorna True se a linha é cabeçalho, total ou separador — deve ser ignorada."""
    skip_patterns = [
        "data pag", "data recebimento", "descri", "companhias",
        "total", "saldo", "banco itau", "banco sicredi", "banco sicred",
        "gastos fix", "gastos variav", "recebimento", "custo aguas",
        "agronegocio", "investimentos prolongados", "nan",
        "resultado", "acerto",
    ]
    v0 = str(val_col0).lower()
    v1 = str(val_col1).lower()
    return any(p in v0 or p in v1 for p in skip_patterns)


def extrair_valor(row: pd.Series) -> float | None:
    """Extrai valor numérico das colunas de débito/crédito (col 2, 3, 4, 5)."""
    for col in [2, 3, 4, 5]:
        val = row.get(col)
        if val is not None and pd.notna(val):
            if isinstance(val, (int, float)) and val != 0:
                return abs(float(val))
            if isinstance(val, str):
                limpo = re.sub(r"[R$\s\.]", "", val).replace(",", ".")
                try:
                    v = float(limpo)
                    if v != 0:
                        return abs(v)
                except ValueError:
                    pass
    return None


def parsear_aba(df: pd.DataFrame, nome_aba: str) -> list[Lancamento]:
    """Parseia uma aba do balancete e retorna lista de lançamentos."""
    lancamentos: list[Lancamento] = []
    secao_atual = ""

    for i, row in df.iterrows():
        val0 = str(row.get(0, "")).strip()
        val1 = str(row.get(1, "")).strip()

        if val0 in ("nan", "None", "") and val1 in ("nan", "None", ""):
            continue

        # Detecta mudança de seção
        nova_secao = detectar_secao(val0, val1, secao_atual)
        if nova_secao != secao_atual:
            secao_atual = nova_secao
            continue

        # Ignora cabeçalhos e totais
        if e_linha_header_ou_total(val0, val1):
            continue

        # Precisa ter data ou descrição válida
        descricao = val1 if val1 not in ("nan", "None", "") else val0
        if descricao in ("nan", "None", ""):
            continue

        # Parse de data
        data_pag: date | None = None
        try:
            if isinstance(row.get(0), datetime):
                data_pag = row.get(0).date()
            elif val0 not in ("nan", "None", ""):
                data_pag = pd.to_datetime(val0, dayfirst=True, errors="coerce")
                data_pag = data_pag.date() if pd.notna(data_pag) else None
        except Exception:
            data_pag = None

        # Valor
        valor = extrair_valor(row)

        # Classificação
        classif = classificar(descricao, secao_atual)

        # Seguradora (para receitas)
        seguradora_nome = ""
        if classif["tipo_lancamento"] == "receita":
            desc_lower = descricao.lower()
            for seg in sorted(SEGURADORAS, key=len, reverse=True):
                if seg in desc_lower:
                    seguradora_nome = seg.title()
                    break

        # Motivo de revisão
        motivo = ""
        if classif["tipo_lancamento"] == "revisar":
            motivo = "descricao nao mapeada no dicionario"
        elif valor is None:
            motivo = "valor nao preenchido na planilha"

        lancamentos.append(Lancamento(
            data_pag=data_pag,
            descricao=descricao,
            valor=valor,
            secao=secao_atual,
            aba=nome_aba,
            linha_excel=int(i) + 1,
            categoria=classif["categoria"],
            subcategoria=classif["subcategoria"],
            tipo=classif["tipo_lancamento"],
            centro_custo=classif["centro_custo"],
            seguradora_nome=seguradora_nome,
            motivo_revisar=motivo,
        ))

    return lancamentos


# ── IMPORTAÇÃO PARA SUPABASE ──────────────────────────────────

def importar_para_banco(
    lancamentos: list[Lancamento],
    supabase: Client,
    competencia: date,
    dry_run: bool = False,
) -> dict[str, int]:
    """Importa lançamentos classificados para as tabelas do Supabase."""
    stats = {"despesas": 0, "receitas": 0, "impostos": 0, "ignorados": 0, "erros": 0}

    # Cache de seguradoras
    segs = supabase.table("seguradoras").select("id,nome").execute()
    seg_map = {s["nome"].lower(): s["id"] for s in segs.data}

    # Ramo padrão (AUTO) para comissões sem ramo definido
    ramo_auto = supabase.table("ramos").select("id").eq("codigo", "AUTO").limit(1).execute()
    ramo_id = ramo_auto.data[0]["id"] if ramo_auto.data else None

    # Cliente genérico para comissões sem apólice identificada
    cliente_generico = supabase.table("clientes").select("id") \
        .eq("nome", "Cliente Generico ETL").limit(1).execute()
    if not cliente_generico.data:
        if not dry_run:
            r = supabase.table("clientes").insert({"nome": "Cliente Generico ETL", "tipo": "pj"}).execute()
            cliente_id = r.data[0]["id"]
        else:
            cliente_id = "00000000-0000-0000-0000-000000000000"
    else:
        cliente_id = cliente_generico.data[0]["id"]

    # Produtor genérico
    prod_gen = supabase.table("produtores").select("id") \
        .eq("nome", "Producao Geral").limit(1).execute()
    if not prod_gen.data:
        if not dry_run:
            r = supabase.table("produtores").insert({"nome": "Producao Geral", "tipo": "interno", "ativo": True}).execute()
            produtor_id = r.data[0]["id"]
        else:
            produtor_id = "00000000-0000-0000-0000-000000000001"
    else:
        produtor_id = prod_gen.data[0]["id"]

    for lanc in lancamentos:
        if lanc.tipo == "revisar" or lanc.motivo_revisar:
            stats["ignorados"] += 1
            continue

        if lanc.valor is None:
            stats["ignorados"] += 1
            continue

        try:
            if lanc.tipo == "despesa":
                registro = {
                    "categoria":    lanc.categoria,
                    "subcategoria": lanc.subcategoria,
                    "descricao":    lanc.descricao,
                    "valor":        lanc.valor,
                    "competencia":  competencia.isoformat(),
                    "paga_em":      lanc.data_pag.isoformat() if lanc.data_pag else None,
                    "centro_custo": lanc.centro_custo,
                    "recorrente":   False,
                }
                if not dry_run:
                    supabase.table("despesas").insert(registro).execute()
                stats["despesas"] += 1

            elif lanc.tipo == "imposto":
                registro = {
                    "tipo":          lanc.subcategoria,
                    "competencia":   competencia.isoformat(),
                    "base_calculo":  lanc.valor,
                    "aliquota":      0,
                    "valor":         lanc.valor,
                    "pago_em":       lanc.data_pag.isoformat() if lanc.data_pag else None,
                }
                if not dry_run:
                    supabase.table("impostos").insert(registro).execute()
                stats["impostos"] += 1

            elif lanc.tipo == "receita":
                # Para receitas de seguradora: cria apólice genérica + comissão
                seg_id = None
                if lanc.seguradora_nome:
                    seg_id = seg_map.get(lanc.seguradora_nome.lower())

                if seg_id and ramo_id:
                    if not dry_run:
                        apolice = supabase.table("apolices").insert({
                            "numero":          f"ETL-{competencia.strftime('%Y%m')}-{lanc.linha_excel}",
                            "seguradora_id":   seg_id,
                            "ramo_id":         ramo_id,
                            "cliente_id":      cliente_id,
                            "produtor_id":     produtor_id,
                            "premio_total":    lanc.valor,
                            "inicio_vigencia": competencia.isoformat(),
                            "fim_vigencia":    competencia.replace(year=competencia.year + 1).isoformat(),
                            "emitida_em":      competencia.isoformat(),
                            "status":          "ativa",
                        }).execute()
                        apolice_id = apolice.data[0]["id"]

                        supabase.table("comissoes").insert({
                            "apolice_id":  apolice_id,
                            "tipo":        "comissao_padrao",
                            "valor":       lanc.valor,
                            "competencia": competencia.isoformat(),
                            "recebida_em": lanc.data_pag.isoformat() if lanc.data_pag else None,
                        }).execute()
                    stats["receitas"] += 1

        except Exception as e:
            print(f"    [ERRO] Linha {lanc.linha_excel}: {e}")
            stats["erros"] += 1

    return stats


# ── RELATÓRIOS ────────────────────────────────────────────────

def gerar_csvs(lancamentos: list[Lancamento]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    todos = []
    revisar = []

    for lanc in lancamentos:
        row = {
            "aba":           lanc.aba,
            "linha_excel":   lanc.linha_excel,
            "data_pag":      lanc.data_pag,
            "descricao":     lanc.descricao,
            "valor":         lanc.valor if lanc.valor is not None else "",
            "secao":         lanc.secao,
            "tipo":          lanc.tipo,
            "categoria":     lanc.categoria,
            "subcategoria":  lanc.subcategoria,
            "centro_custo":  lanc.centro_custo,
            "seguradora":    lanc.seguradora_nome,
        }
        todos.append(row)
        if lanc.tipo == "revisar" or lanc.valor is None:
            row_rev = row.copy()
            row_rev["motivo"] = lanc.motivo_revisar or "valor ausente"
            revisar.append(row_rev)

    pd.DataFrame(todos).to_csv(OUTPUT_DIR / "lancamentos_importados.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(revisar).to_csv(OUTPUT_DIR / "revisar.csv", index=False, encoding="utf-8-sig")
    print(f"\n  [OK] lancamentos_importados.csv  ({len(todos)} linhas)")
    print(f"  [OK] revisar.csv                 ({len(revisar)} linhas para revisao)")


def gerar_relatorio(lancamentos: list[Lancamento], stats: dict, competencia: date) -> None:
    total = len(lancamentos)
    sem_valor = sum(1 for l in lancamentos if l.valor is None)
    revisao = sum(1 for l in lancamentos if l.tipo == "revisar")
    pct_revisao = round(revisao / total * 100, 1) if total else 0

    por_tipo: dict[str, int] = {}
    por_categoria: dict[str, float] = {}
    for l in lancamentos:
        por_tipo[l.tipo] = por_tipo.get(l.tipo, 0) + 1
        if l.valor:
            por_categoria[l.categoria or l.tipo] = \
                por_categoria.get(l.categoria or l.tipo, 0) + l.valor

    md = f"""# MIGRACAO_2026.md — Relatório de Migração ETL

**Gerado em:** {date.today()}
**Competência:** {competencia.strftime('%B/%Y')}
**Arquivo origem:** Balancete 2026 (Itau).xlsx

---

## Resumo

| Métrica | Valor |
|---|---|
| Total de lançamentos lidos | {total} |
| Sem valor preenchido | {sem_valor} |
| Necessitam revisão manual | {revisao} ({pct_revisao}%) |
| Despesas importadas | {stats.get('despesas', 0)} |
| Receitas importadas | {stats.get('receitas', 0)} |
| Impostos importados | {stats.get('impostos', 0)} |
| Erros na importação | {stats.get('erros', 0)} |

---

## Distribuição por tipo

| Tipo | Quantidade |
|---|---|
{"".join(f'| {k} | {v} |' + chr(10) for k, v in sorted(por_tipo.items(), key=lambda x: -x[1]))}

---

## Premissas assumidas

1. **Regime de caixa**: datas usadas são as do extrato bancário (coluna A).
2. **Competência**: definida como o mês da aba (`{competencia.strftime('%Y-%m')}-01`).
3. **Receitas de seguradoras**: cada linha de recebimento virou uma apólice genérica
   (`numero = ETL-YYYYMM-LINHA`) + comissão do tipo `comissao_padrao`.
   Ramo padrão: AUTO — revisar linhas onde o ramo real é diferente.
4. **Rodrigo Robles** classificado como `terceiros / repasse_produtor` (produtor AGRO).
5. **Águas de Lindoia**: despesas da seção "Custo Aguas de Lindoia" recebem
   `centro_custo = 'aguas_lindoia'`.
6. **Valores ausentes**: lançamentos sem valor (R$) foram listados em `revisar.csv`
   mas NÃO importados para o banco. Preencha os valores no Excel e rode novamente.

---

## Como completar a migração

1. Abra `Balancete 2026 (Itau).xlsx`
2. Preencha a coluna **C (Débito)** para despesas e **C (Crédito)** para receitas
3. Salve o arquivo
4. Execute novamente: `python etl/import_balancete.py`

---

## Arquivos gerados

- `data/output/lancamentos_importados.csv` — todos os lançamentos parseados
- `data/output/revisar.csv` — lançamentos sem valor ou sem classificação
"""
    caminho = Path(__file__).parent / "MIGRACAO_2026.md"
    caminho.write_text(md, encoding="utf-8")
    print(f"  [OK] MIGRACAO_2026.md")


# ── MAIN ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ETL Balancete 2026 — MX Seguros")
    parser.add_argument("--arquivo",   default=str(ARQUIVO_PADRAO))
    parser.add_argument("--dry-run",   action="store_true",
                        help="Processa sem gravar no banco")
    args = parser.parse_args()

    print("=" * 55)
    print("  MX Seguros DRE-IA — ETL Balancete 2026")
    print("=" * 55)
    if args.dry_run:
        print("  [DRY-RUN] Nenhum dado sera gravado no banco")
    print()

    arquivo = Path(args.arquivo)
    if not arquivo.exists():
        print(f"  [ERRO] Arquivo nao encontrado: {arquivo}")
        sys.exit(1)

    # Lê todas as abas
    xl = pd.ExcelFile(arquivo)
    print(f"  Arquivo: {arquivo.name}")
    print(f"  Abas:    {xl.sheet_names}")
    print()

    todos_lancamentos: list[Lancamento] = []

    for nome_aba in xl.sheet_names:
        print(f"  Processando aba: {nome_aba}")
        df = pd.read_excel(arquivo, sheet_name=nome_aba, header=None)
        lancamentos_aba = parsear_aba(df, nome_aba)
        todos_lancamentos.extend(lancamentos_aba)
        print(f"    {len(lancamentos_aba)} lancamentos extraidos")

    print(f"\n  Total: {len(todos_lancamentos)} lancamentos")

    # Gera CSVs
    gerar_csvs(todos_lancamentos)

    # Importa para banco (se não for dry-run)
    supabase = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

    # Competência = primeiro dia do mês da aba
    competencia = date(2026, 5, 1)

    print("\n  Importando para o Supabase...")
    stats = importar_para_banco(todos_lancamentos, supabase, competencia, dry_run=args.dry_run)

    # Relatório
    gerar_relatorio(todos_lancamentos, stats, competencia)

    print()
    print("=" * 55)
    print(f"  Despesas importadas:  {stats['despesas']}")
    print(f"  Receitas importadas:  {stats['receitas']}")
    print(f"  Impostos importados:  {stats['impostos']}")
    print(f"  Aguardando revisao:   {stats['ignorados']} (sem valor na planilha)")
    print(f"  Erros:                {stats['erros']}")
    print("=" * 55)

    if stats["ignorados"] > 0:
        print()
        print("  PROXIMOS PASSOS:")
        print("  1. Preencha os valores (R$) no arquivo Excel")
        print("  2. Execute novamente: python etl/import_balancete.py")
        print()
        print("  Ver lancamentos pendentes: data/output/revisar.csv")


if __name__ == "__main__":
    main()
