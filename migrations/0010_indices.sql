-- =============================================================
-- MX Seguros — DRE-IA | Migration 0010: Índices de Performance
-- Sprint 1 — Onda 1 (§1.5 da Revisão Técnica)
-- =============================================================
-- Problema: dre_por_periodo() faz 6 sub-queries independentes.
-- Cada uma faz range-scan em tabelas que podem ter >100k linhas.
-- Os índices simples existentes em competencia/status NÃO cobrem
-- queries com duas colunas de filtro simultâneas — o Postgres
-- precisa de um index merge (mais lento).
-- Solução: índices compostos que permitem single-index scan.
-- =============================================================

-- ── ÍNDICES JÁ EXISTENTES (referência, não recriar) ──────────
-- idx_comissoes_competencia  ON comissoes(competencia)
-- idx_comissoes_apolice      ON comissoes(apolice_id)
-- idx_estornos_competencia   ON estornos(competencia_estorno)
-- idx_repasses_competencia   ON repasses(competencia)
-- idx_repasses_status        ON repasses(status)
-- idx_apolices_equipe        ON apolices(equipe_id)
-- idx_apolices_produtor      ON apolices(produtor_id)
-- idx_apolices_emitida_em    ON apolices(emitida_em)
-- idx_despesas_competencia   ON despesas(competencia)
-- idx_despesas_status        ON despesas(status)         [0006]
-- idx_despesas_criado_por    ON despesas(criado_por)     [0006]


-- ── 1. COMISSÕES ─────────────────────────────────────────────
-- Cobrindo o JOIN apolice_id + filtro de período em uma leitura.
CREATE INDEX IF NOT EXISTS idx_comissoes_apolice_competencia
  ON comissoes(apolice_id, competencia);

-- Índice funcional para o padrão DATE_TRUNC('month', competencia)
-- usado em dre_por_periodo(), receita_por_ramo() e atingimento_metas().
CREATE INDEX IF NOT EXISTS idx_comissoes_mes_valor
  ON comissoes(date_trunc('month', competencia), valor);


-- ── 2. ESTORNOS ──────────────────────────────────────────────
-- Cobre o JOIN apolice_id + filtro de período.
CREATE INDEX IF NOT EXISTS idx_estornos_apolice_competencia
  ON estornos(apolice_id, competencia_estorno);

-- Índice funcional alinhado com o padrão da função.
CREATE INDEX IF NOT EXISTS idx_estornos_mes
  ON estornos(date_trunc('month', competencia_estorno));


-- ── 3. REPASSES ──────────────────────────────────────────────
-- Substitui o index merge entre idx_repasses_competencia e
-- idx_repasses_status: agora um único B-tree cobre ambos.
CREATE INDEX IF NOT EXISTS idx_repasses_competencia_status
  ON repasses(competencia, status);

-- Índice funcional + status — alinhado com o filtro do DRE.
CREATE INDEX IF NOT EXISTS idx_repasses_mes_status
  ON repasses(date_trunc('month', competencia), status);


-- ── 4. DESPESAS ──────────────────────────────────────────────
-- Cobre competencia + status (fluxo de aprovação) + categoria (DRE).
CREATE INDEX IF NOT EXISTS idx_despesas_competencia_status
  ON despesas(competencia, status);

CREATE INDEX IF NOT EXISTS idx_despesas_competencia_categoria
  ON despesas(competencia, categoria);

-- Funcional para o padrão DATE_TRUNC usado no DRE.
CREATE INDEX IF NOT EXISTS idx_despesas_mes_categoria
  ON despesas(date_trunc('month', competencia), categoria);


-- ── 5. IMPOSTOS ──────────────────────────────────────────────
-- Não existia nenhum índice em impostos — seq scan garantido.
CREATE INDEX IF NOT EXISTS idx_impostos_competencia
  ON impostos(competencia);

CREATE INDEX IF NOT EXISTS idx_impostos_mes
  ON impostos(date_trunc('month', competencia));


-- ── 6. APÓLICES ──────────────────────────────────────────────
-- JOINs de RLS combinam equipe_id + produtor_id constantemente.
-- O Postgres hoje faz OR de dois índices simples; este elimina isso.
CREATE INDEX IF NOT EXISTS idx_apolices_equipe_produtor
  ON apolices(equipe_id, produtor_id);

-- Ramo é usado em receita_por_ramo() e atingimento_metas().
CREATE INDEX IF NOT EXISTS idx_apolices_ramo_id
  ON apolices(ramo_id);


-- ── 7. RECEITAS OUTRAS ───────────────────────────────────────
-- dre_por_periodo() inclui receitas_outras desde migration 0005.
CREATE INDEX IF NOT EXISTS idx_receitas_outras_mes
  ON receitas_outras(date_trunc('month', competencia));


-- ── 8. AUDIT LOG ─────────────────────────────────────────────
-- Consultas admin filtram por acao + período.
CREATE INDEX IF NOT EXISTS idx_audit_acao_criado_em
  ON audit_log(acao, criado_em);


-- =============================================================
-- VERIFICAÇÃO: rode após aplicar para confirmar os planos.
--
-- EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
-- SELECT * FROM dre_por_periodo('2026-01-01'::date, '2026-03-31'::date);
--
-- Esperado: "Index Scan" ou "Bitmap Index Scan" em comissoes,
-- estornos, repasses, despesas e impostos.
-- "Seq Scan" nessas tabelas é sinal de que o dado é pequeno
-- demais para o planner preferir índice (< ~1000 linhas).
-- =============================================================
