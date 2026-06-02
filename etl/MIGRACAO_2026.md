# MIGRACAO_2026.md — Relatório de Migração ETL

**Gerado em:** 2026-05-27
**Competência:** May/2026
**Arquivo origem:** Balancete 2026 (Itau).xlsx

---

## Resumo

| Métrica | Valor |
|---|---|
| Total de lançamentos lidos | 381 |
| Sem valor preenchido | 381 |
| Necessitam revisão manual | 1 (0.3%) |
| Despesas importadas | 0 |
| Receitas importadas | 0 |
| Impostos importados | 0 |
| Erros na importação | 0 |

---

## Distribuição por tipo

| Tipo | Quantidade |
|---|---|
| receita | 243 |
| despesa | 125 |
| imposto | 7 |
| investimento | 5 |
| revisar | 1 |


---

## Premissas assumidas

1. **Regime de caixa**: datas usadas são as do extrato bancário (coluna A).
2. **Competência**: definida como o mês da aba (`2026-05-01`).
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
