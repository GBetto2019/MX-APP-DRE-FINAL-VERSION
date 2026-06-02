-- =============================================================
-- MX Seguros — DRE-IA | Migration 0003: Funções SQL
-- Fase 1 | Cálculo canônico do DRE e funções auxiliares
-- =============================================================

-- ── FUNÇÃO PRINCIPAL: DRE por período ────────────────────────
-- SECURITY INVOKER: roda com as permissões do usuário chamador.
-- O RLS filtra automaticamente o que ele pode ver.
-- Comercial chamando esta função verá apenas suas próprias comissões.

CREATE OR REPLACE FUNCTION dre_por_periodo(p_inicio DATE, p_fim DATE)
RETURNS JSONB AS $$
DECLARE
  resultado JSONB;
BEGIN
  WITH
  receita AS (
    SELECT COALESCE(SUM(c.valor), 0) AS total
    FROM comissoes c
    WHERE DATE_TRUNC('month', c.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio)
              AND DATE_TRUNC('month', p_fim)
  ),
  estornos_periodo AS (
    SELECT COALESCE(SUM(e.valor), 0) AS total
    FROM estornos e
    WHERE DATE_TRUNC('month', e.competencia_estorno)
          BETWEEN DATE_TRUNC('month', p_inicio)
              AND DATE_TRUNC('month', p_fim)
  ),
  impostos_periodo AS (
    SELECT COALESCE(SUM(i.valor), 0) AS total
    FROM impostos i
    WHERE DATE_TRUNC('month', i.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio)
              AND DATE_TRUNC('month', p_fim)
  ),
  repasses_periodo AS (
    SELECT COALESCE(SUM(r.valor), 0) AS total
    FROM repasses r
    WHERE DATE_TRUNC('month', r.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio)
              AND DATE_TRUNC('month', p_fim)
      AND r.status != 'estornado'
  ),
  despesas_fixas AS (
    SELECT COALESCE(SUM(d.valor), 0) AS total
    FROM despesas d
    WHERE DATE_TRUNC('month', d.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio)
              AND DATE_TRUNC('month', p_fim)
      AND d.categoria IN (
        'pessoal', 'comercial', 'administrativa_operacional',
        'veiculos', 'terceiros', 'financeira'
      )
  ),
  despesas_nao_operacionais AS (
    SELECT COALESCE(SUM(d.valor), 0) AS total
    FROM despesas d
    WHERE DATE_TRUNC('month', d.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio)
              AND DATE_TRUNC('month', p_fim)
      AND d.categoria IN ('nao_operacional', 'investimento_imobilizado')
  )
  SELECT jsonb_build_object(
    'periodo', jsonb_build_object(
      'inicio', p_inicio,
      'fim',    p_fim
    ),
    'receita_bruta',          (SELECT total FROM receita),
    'estornos',               (SELECT total FROM estornos_periodo),
    'impostos',               (SELECT total FROM impostos_periodo),
    'receita_liquida',        (SELECT total FROM receita)
                              - (SELECT total FROM estornos_periodo)
                              - (SELECT total FROM impostos_periodo),
    'repasses_produtores',    (SELECT total FROM repasses_periodo),
    'margem_contribuicao',    (SELECT total FROM receita)
                              - (SELECT total FROM estornos_periodo)
                              - (SELECT total FROM impostos_periodo)
                              - (SELECT total FROM repasses_periodo),
    'despesas_fixas',         (SELECT total FROM despesas_fixas),
    'ebitda',                 (SELECT total FROM receita)
                              - (SELECT total FROM estornos_periodo)
                              - (SELECT total FROM impostos_periodo)
                              - (SELECT total FROM repasses_periodo)
                              - (SELECT total FROM despesas_fixas),
    'despesas_nao_operacionais', (SELECT total FROM despesas_nao_operacionais),
    'resultado_liquido',      (SELECT total FROM receita)
                              - (SELECT total FROM estornos_periodo)
                              - (SELECT total FROM impostos_periodo)
                              - (SELECT total FROM repasses_periodo)
                              - (SELECT total FROM despesas_fixas)
                              - (SELECT total FROM despesas_nao_operacionais)
  ) INTO resultado;

  RETURN resultado;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER STABLE;

-- ── FUNÇÃO: Receita por ramo no período ───────────────────────

CREATE OR REPLACE FUNCTION receita_por_ramo(p_inicio DATE, p_fim DATE)
RETURNS JSONB AS $$
  -- Subconsulta calcula os agregados primeiro; jsonb_agg só monta o JSON
  SELECT jsonb_agg(
    jsonb_build_object(
      'ramo_codigo',  ramo_codigo,
      'ramo_nome',    ramo_nome,
      'receita_total', receita_total,
      'num_apolices',  num_apolices
    )
    ORDER BY receita_total DESC NULLS LAST
  )
  FROM (
    SELECT
      r.codigo                          AS ramo_codigo,
      r.nome                            AS ramo_nome,
      COALESCE(SUM(c.valor), 0)         AS receita_total,
      COUNT(DISTINCT a.id)              AS num_apolices
    FROM ramos r
    LEFT JOIN apolices a ON a.ramo_id = r.id
    LEFT JOIN comissoes c ON c.apolice_id = a.id
      AND DATE_TRUNC('month', c.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio)
              AND DATE_TRUNC('month', p_fim)
    GROUP BY r.id, r.codigo, r.nome
  ) sub
$$ LANGUAGE sql SECURITY INVOKER STABLE;

-- ── FUNÇÃO: Taxa de estorno do período ───────────────────────
-- Dispara alerta se > 5% (ver §4.2 do escopo)

CREATE OR REPLACE FUNCTION taxa_estorno(p_inicio DATE, p_fim DATE)
RETURNS JSONB AS $$
DECLARE
  v_receita  NUMERIC(14,2);
  v_estorno  NUMERIC(14,2);
  v_taxa     NUMERIC(6,4);
  v_alerta   BOOLEAN;
BEGIN
  SELECT COALESCE(SUM(valor), 0) INTO v_receita
  FROM comissoes
  WHERE DATE_TRUNC('month', competencia)
        BETWEEN DATE_TRUNC('month', p_inicio)
            AND DATE_TRUNC('month', p_fim);

  SELECT COALESCE(SUM(valor), 0) INTO v_estorno
  FROM estornos
  WHERE DATE_TRUNC('month', competencia_estorno)
        BETWEEN DATE_TRUNC('month', p_inicio)
            AND DATE_TRUNC('month', p_fim);

  v_taxa   := CASE WHEN v_receita > 0 THEN v_estorno / v_receita ELSE 0 END;
  v_alerta := v_taxa > 0.05;

  RETURN jsonb_build_object(
    'receita_bruta',      v_receita,
    'total_estornos',     v_estorno,
    'taxa_estorno',       v_taxa,
    'taxa_percentual',    ROUND(v_taxa * 100, 2),
    'alerta_5pct',        v_alerta
  );
END;
$$ LANGUAGE plpgsql SECURITY INVOKER STABLE;

-- ── FUNÇÃO: Comissões por produtor ───────────────────────────

CREATE OR REPLACE FUNCTION comissoes_por_produtor(
  p_inicio     DATE,
  p_fim        DATE,
  p_produtor   UUID DEFAULT NULL
)
RETURNS JSONB AS $$
  -- Subconsulta calcula os agregados; jsonb_agg só monta o JSON
  SELECT jsonb_agg(
    jsonb_build_object(
      'produtor_id',    produtor_id,
      'produtor_nome',  produtor_nome,
      'total_comissao', total_comissao,
      'num_apolices',   num_apolices,
      'total_repasse',  total_repasse
    )
    ORDER BY total_comissao DESC NULLS LAST
  )
  FROM (
    SELECT
      p.id                              AS produtor_id,
      p.nome                            AS produtor_nome,
      COALESCE(SUM(c.valor), 0)         AS total_comissao,
      COUNT(DISTINCT a.id)              AS num_apolices,
      COALESCE(SUM(r.valor), 0)         AS total_repasse
    FROM produtores p
    LEFT JOIN apolices a ON a.produtor_id = p.id
    LEFT JOIN comissoes c ON c.apolice_id = a.id
      AND DATE_TRUNC('month', c.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio)
              AND DATE_TRUNC('month', p_fim)
    LEFT JOIN repasses r ON r.comissao_id = c.id
      AND r.status != 'estornado'
    WHERE (p_produtor IS NULL OR p.id = p_produtor)
    GROUP BY p.id, p.nome
  ) sub
$$ LANGUAGE sql SECURITY INVOKER STABLE;

-- ── FUNÇÃO: Atingimento de metas ─────────────────────────────

CREATE OR REPLACE FUNCTION atingimento_metas(p_competencia DATE)
RETURNS JSONB AS $$
  SELECT jsonb_agg(
    jsonb_build_object(
      'meta_id',       m.id,
      'escopo',        m.escopo,
      'escopo_id',     m.escopo_id,
      'metrica',       m.metrica,
      'valor_alvo',    m.valor_alvo,
      'valor_atual',   COALESCE(realizado.total, 0),
      'percentual',    CASE
                         WHEN m.valor_alvo > 0
                         THEN ROUND((COALESCE(realizado.total, 0) / m.valor_alvo) * 100, 2)
                         ELSE 0
                       END,
      'atingida',      COALESCE(realizado.total, 0) >= m.valor_alvo
    )
  )
  FROM metas m
  LEFT JOIN LATERAL (
    SELECT COALESCE(SUM(c.valor), 0) AS total
    FROM comissoes c
    JOIN apolices a ON a.id = c.apolice_id
    WHERE DATE_TRUNC('month', c.competencia) = DATE_TRUNC('month', p_competencia)
      AND CASE m.escopo
            WHEN 'global'    THEN true
            WHEN 'equipe'    THEN a.equipe_id   = m.escopo_id
            WHEN 'produtor'  THEN a.produtor_id = m.escopo_id
            WHEN 'ramo'      THEN a.ramo_id     = m.escopo_id
            ELSE false
          END
  ) realizado ON true
  WHERE DATE_TRUNC('month', m.competencia) = DATE_TRUNC('month', p_competencia)
$$ LANGUAGE sql SECURITY INVOKER STABLE;
