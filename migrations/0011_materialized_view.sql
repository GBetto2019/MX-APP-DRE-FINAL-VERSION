-- =============================================================
-- MX Seguros — DRE-IA | Migration 0011: Materialized View DRE
-- Sprint 1 — Onda 1 (§1.2 da Revisão Técnica)
-- =============================================================
-- Problema: dre_por_periodo() recalcula tudo do zero a cada
-- chamada (~200-500ms). Meses fechados nunca mudam.
-- Solução: mv_dre_mensal pré-agrega os componentes do DRE por
-- mês, equipe e produtor. Consultas históricas passam de
-- "6 full-scans" para "1 index scan" (~5ms).
--
-- Estrutura de duas views complementares:
--   mv_dre_receita_mensal — componentes de receita (têm contexto
--                           equipe/produtor, respeitam RLS)
--   mv_dre_custos_mensais — custos da corretora (sem contexto
--                           equipe/produtor, nível admin/contador)
--
-- A função dre_por_periodo() (migration 0003 / 0005) será
-- atualizada no Sprint 3 para ler dessas views em meses fechados.
-- =============================================================


-- ── VIEW 1: Receita por equipe × produtor × mês ──────────────
-- Dimensão equipe_id / produtor_id mantém compatibilidade com RLS.
-- O NULL em equipe_id ou produtor_id representa totais parciais
-- (GROUPING SETS não usado aqui para simplificar o acesso).

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dre_receita_mensal AS
WITH comissoes_agg AS (
  SELECT
    date_trunc('month', c.competencia)::date AS mes,
    a.equipe_id,
    a.produtor_id,
    SUM(c.valor)                              AS receita_comissoes
  FROM comissoes c
  JOIN apolices a ON a.id = c.apolice_id
  GROUP BY 1, 2, 3
),
receitas_outras_agg AS (
  -- Receitas manuais não têm equipe/produtor: distribuídas por mês.
  SELECT
    date_trunc('month', ro.competencia)::date AS mes,
    SUM(ro.valor)                              AS receita_outras
  FROM receitas_outras ro
  GROUP BY 1
),
estornos_agg AS (
  SELECT
    date_trunc('month', e.competencia_estorno)::date AS mes,
    a.equipe_id,
    a.produtor_id,
    SUM(e.valor)                                      AS total_estornos
  FROM estornos e
  JOIN apolices a ON a.id = e.apolice_id
  GROUP BY 1, 2, 3
),
repasses_agg AS (
  SELECT
    date_trunc('month', r.competencia)::date AS mes,
    r.produtor_id,
    SUM(r.valor) FILTER (WHERE r.status != 'estornado') AS total_repasses
  FROM repasses r
  GROUP BY 1, 2
)
SELECT
  ca.mes,
  ca.equipe_id,
  ca.produtor_id,
  ca.receita_comissoes,
  COALESCE(roa.receita_outras,   0)  AS receita_outras,
  COALESCE(ea.total_estornos,    0)  AS total_estornos,
  COALESCE(ra.total_repasses,    0)  AS total_repasses,
  -- Linhas derivadas (pré-calculadas para evitar aritmética na leitura)
  ca.receita_comissoes
    + COALESCE(roa.receita_outras, 0)
    - COALESCE(ea.total_estornos, 0) AS receita_liquida_sem_impostos
FROM comissoes_agg ca
LEFT JOIN receitas_outras_agg roa ON roa.mes = ca.mes
LEFT JOIN estornos_agg ea
  ON ea.mes          = ca.mes
 AND ea.equipe_id    = ca.equipe_id
 AND ea.produtor_id  = ca.produtor_id
LEFT JOIN repasses_agg ra
  ON ra.mes         = ca.mes
 AND ra.produtor_id = ca.produtor_id;


-- ── VIEW 2: Custos corretora × mês ───────────────────────────
-- Impostos e despesas não têm granularidade equipe/produtor.
-- Admin e Contador veem tudo; Gestor e Comercial não veem custos
-- no DRE — portanto não há problema em não ter a dimensão aqui.

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dre_custos_mensais AS
WITH impostos_agg AS (
  SELECT
    date_trunc('month', i.competencia)::date AS mes,
    SUM(i.valor)                              AS total_impostos
  FROM impostos i
  GROUP BY 1
),
despesas_agg AS (
  SELECT
    date_trunc('month', d.competencia)::date AS mes,
    -- Despesas fixas: categorias legadas OU tipo_lancamento custo_tipo fixo/variável
    SUM(d.valor) FILTER (
      WHERE d.categoria IN (
        'pessoal', 'comercial', 'administrativa_operacional',
        'veiculos', 'terceiros', 'financeira'
      )
      OR (d.tipo_lancamento_id IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM tipos_lancamento tl
             WHERE tl.id = d.tipo_lancamento_id
               AND tl.custo_tipo IN ('fixo', 'variavel')
          )
        )
    ) AS despesas_fixas,
    -- Despesas não-operacionais: categorias legadas OU tipo custo_tipo nao_operacional
    SUM(d.valor) FILTER (
      WHERE d.categoria IN ('nao_operacional', 'investimento_imobilizado')
      OR (d.tipo_lancamento_id IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM tipos_lancamento tl
             WHERE tl.id = d.tipo_lancamento_id
               AND tl.custo_tipo = 'nao_operacional'
          )
        )
    ) AS despesas_nao_operacionais
  FROM despesas d
  WHERE d.status != 'rejeitada'   -- excluir despesas rejeitadas do DRE
  GROUP BY 1
)
SELECT
  COALESCE(ia.mes, da.mes)             AS mes,
  COALESCE(ia.total_impostos,       0) AS total_impostos,
  COALESCE(da.despesas_fixas,       0) AS despesas_fixas,
  COALESCE(da.despesas_nao_operacionais, 0) AS despesas_nao_operacionais
FROM impostos_agg ia
FULL OUTER JOIN despesas_agg da ON da.mes = ia.mes;


-- ── ÍNDICES DAS VIEWS ────────────────────────────────────────
-- UNIQUE obrigatório para REFRESH CONCURRENTLY (sem lock exclusivo).

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dre_receita_pk
  ON mv_dre_receita_mensal(mes, equipe_id, produtor_id);

-- Índice de apoio para consultas que filtram só por mês.
CREATE INDEX IF NOT EXISTS idx_mv_dre_receita_mes
  ON mv_dre_receita_mensal(mes);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dre_custos_pk
  ON mv_dre_custos_mensais(mes);


-- ── FUNÇÃO DE REFRESH ────────────────────────────────────────
-- Chamada após importação de dados ou via cron (a cada 5 min).
-- CONCURRENTLY: não bloqueia leituras durante o refresh.

CREATE OR REPLACE FUNCTION refresh_mv_dre()
RETURNS VOID AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dre_receita_mensal;
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dre_custos_mensais;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ── COMENTÁRIOS DE DOCUMENTAÇÃO ──────────────────────────────

COMMENT ON MATERIALIZED VIEW mv_dre_receita_mensal IS
  'Pré-agrega receita de comissões, outras receitas, estornos e repasses
   por mês × equipe × produtor. Usada por dre_por_periodo() para meses
   fechados. Refresh via refresh_mv_dre(). Sprint 1 — Onda 1.';

COMMENT ON MATERIALIZED VIEW mv_dre_custos_mensais IS
  'Pré-agrega impostos e despesas (fixas e não-operacionais) por mês.
   Visível apenas a Admin/Contador no DRE. Sprint 1 — Onda 1.';


-- =============================================================
-- REFRESH INICIAL (popula as views após criar)
-- Execute manualmente ou via executar_migrations.py:
--
--   SELECT refresh_mv_dre();
--
-- VERIFICAÇÃO:
--   SELECT COUNT(*) FROM mv_dre_receita_mensal;
--   SELECT COUNT(*) FROM mv_dre_custos_mensais;
--   SELECT * FROM mv_dre_receita_mensal ORDER BY mes DESC LIMIT 5;
-- =============================================================
