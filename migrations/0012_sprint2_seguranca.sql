-- =============================================================
-- MX Seguros — DRE-IA | Migration 0012: Sprint 2 — Segurança e Regras
-- =============================================================
-- Implementa os 7 itens do Sprint 2 do roadmap técnico:
--   1. (já feito em 0002) RLS estornos por produtor para Comercial
--   2. RLS despesas: Gestor não vê categorias sensíveis (pessoal, nao_operacional)
--   3. Soft-delete: status 'excluida' + DEFAULT muda para 'pendente'
--   4. Metas: Comercial apenas SELECT (remove UPDATE/DELETE)
--   5. Fix atingimento_metas() para métrica numero_apolices
--   6. Migração de despesas legadas: popula tipo_lancamento_id via categoria
--   7. status='pendente' como default para não-admin (DEFAULT + dre_por_periodo())
-- =============================================================


-- ── 3. SOFT-DELETE: adicionar 'excluida' ao status de despesas ─

ALTER TABLE despesas
  DROP CONSTRAINT IF EXISTS despesas_status_check;

ALTER TABLE despesas
  ADD CONSTRAINT despesas_status_check
  CHECK (status IN ('pendente', 'aprovada', 'rejeitada', 'excluida'));

-- Default muda para 'pendente' — seguro por padrão.
-- O serviço define explicitamente 'aprovada' para admin/contador.
ALTER TABLE despesas ALTER COLUMN status SET DEFAULT 'pendente';

-- Índice para filtrar excluídas em queries normais
CREATE INDEX IF NOT EXISTS idx_despesas_status_excluida
  ON despesas(status) WHERE status != 'excluida';


-- ── 2. RLS — DESPESAS: Gestor não vê categorias sensíveis ──────

DROP POLICY IF EXISTS despesas_gestor ON despesas;

-- Gestor vê despesas operacionais (NÃO pessoal nem nao_operacional/investimento)
CREATE POLICY despesas_gestor ON despesas
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'gestor'
    AND status != 'excluida'
    -- Exclui via categoria legada
    AND COALESCE(categoria, '') NOT IN ('pessoal', 'nao_operacional', 'investimento_imobilizado')
    -- Exclui via tipos_lancamento (custo_tipo nao_operacional ou categoria pessoal)
    AND (
      tipo_lancamento_id IS NULL
      OR NOT EXISTS (
        SELECT 1 FROM tipos_lancamento tl
        WHERE tl.id = despesas.tipo_lancamento_id
          AND (tl.custo_tipo = 'nao_operacional' OR tl.categoria = 'pessoal')
      )
    )
  );

-- Comercial também não deve ver excluídas
DROP POLICY IF EXISTS despesas_comercial ON despesas;

CREATE POLICY despesas_comercial ON despesas
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'comercial'
    AND criado_por = auth.uid()
    AND status != 'excluida'
  );


-- ── 4. RLS — METAS: Comercial apenas SELECT ──────────────────

-- Remove a permissão de Comercial editar/deletar própria meta.
-- Risco: Comercial poderia ajustar valor_alvo para aparentar 100% atingido.
DROP POLICY IF EXISTS metas_update ON metas;
DROP POLICY IF EXISTS metas_delete ON metas;

CREATE POLICY metas_update ON metas
  FOR UPDATE TO authenticated
  USING (get_meu_role() IN ('admin', 'gestor'));

CREATE POLICY metas_delete ON metas
  FOR DELETE TO authenticated
  USING (get_meu_role() IN ('admin', 'gestor'));


-- ── 5. FIX atingimento_metas(): tratar metrica numero_apolices ─

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
    SELECT
      CASE m.metrica
        -- Conta apólices distintas em vez de somar valor de comissões
        WHEN 'numero_apolices'
          THEN COUNT(DISTINCT a.id)::NUMERIC
        ELSE
          COALESCE(SUM(c.valor), 0)
      END AS total
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


-- ── 6. MIGRAÇÃO: popular tipo_lancamento_id para despesas legadas ─

-- Para cada despesa sem tipo_lancamento_id, associa o primeiro tipo_lancamento
-- correspondente pela categoria. Prioriza tipos específicos sobre genéricos.
UPDATE despesas d
SET tipo_lancamento_id = (
  SELECT tl.id
  FROM tipos_lancamento tl
  WHERE tl.categoria = d.categoria
    AND tl.natureza  = 'despesa'
    AND tl.ativo     = true
  ORDER BY
    -- Tipos genéricos ficam por último (usa o específico se houver)
    CASE tl.nome
      WHEN 'Outras Despesas Fixas'     THEN 2
      WHEN 'Outras Despesas Variáveis' THEN 2
      ELSE 1
    END,
    tl.criado_em
  LIMIT 1
)
WHERE d.tipo_lancamento_id IS NULL
  AND d.categoria IS NOT NULL;


-- ── 7. ATUALIZAR dre_por_periodo(): excluir 'excluida' do DRE ──

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
  receitas_manuais AS (
    SELECT COALESCE(SUM(r.valor), 0) AS total
    FROM receitas_outras r
    WHERE DATE_TRUNC('month', r.competencia)
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
      AND d.status NOT IN ('rejeitada', 'excluida')
      AND (
        (d.tipo_lancamento_id IS NULL AND d.categoria IN (
          'pessoal', 'comercial', 'administrativa_operacional',
          'veiculos', 'terceiros', 'financeira'
        ))
        OR
        (d.tipo_lancamento_id IS NOT NULL AND EXISTS (
          SELECT 1 FROM tipos_lancamento tl
          WHERE tl.id = d.tipo_lancamento_id
            AND tl.custo_tipo IN ('fixo', 'variavel')
        ))
      )
  ),
  despesas_nao_operacionais AS (
    SELECT COALESCE(SUM(d.valor), 0) AS total
    FROM despesas d
    WHERE DATE_TRUNC('month', d.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio)
              AND DATE_TRUNC('month', p_fim)
      AND d.status NOT IN ('rejeitada', 'excluida')
      AND (
        (d.tipo_lancamento_id IS NULL AND d.categoria IN (
          'nao_operacional', 'investimento_imobilizado'
        ))
        OR
        (d.tipo_lancamento_id IS NOT NULL AND EXISTS (
          SELECT 1 FROM tipos_lancamento tl
          WHERE tl.id = d.tipo_lancamento_id
            AND tl.custo_tipo = 'nao_operacional'
        ))
      )
  )
  SELECT jsonb_build_object(
    'periodo', jsonb_build_object(
      'inicio', p_inicio,
      'fim',    p_fim
    ),
    'receita_bruta',
      (SELECT total FROM receita) + (SELECT total FROM receitas_manuais),
    'estornos',
      (SELECT total FROM estornos_periodo),
    'impostos',
      (SELECT total FROM impostos_periodo),
    'receita_liquida',
      (SELECT total FROM receita) + (SELECT total FROM receitas_manuais)
      - (SELECT total FROM estornos_periodo)
      - (SELECT total FROM impostos_periodo),
    'repasses_produtores',
      (SELECT total FROM repasses_periodo),
    'margem_contribuicao',
      (SELECT total FROM receita) + (SELECT total FROM receitas_manuais)
      - (SELECT total FROM estornos_periodo)
      - (SELECT total FROM impostos_periodo)
      - (SELECT total FROM repasses_periodo),
    'despesas_fixas',
      (SELECT total FROM despesas_fixas),
    'ebitda',
      (SELECT total FROM receita) + (SELECT total FROM receitas_manuais)
      - (SELECT total FROM estornos_periodo)
      - (SELECT total FROM impostos_periodo)
      - (SELECT total FROM repasses_periodo)
      - (SELECT total FROM despesas_fixas),
    'despesas_nao_operacionais',
      (SELECT total FROM despesas_nao_operacionais),
    'resultado_liquido',
      (SELECT total FROM receita) + (SELECT total FROM receitas_manuais)
      - (SELECT total FROM estornos_periodo)
      - (SELECT total FROM impostos_periodo)
      - (SELECT total FROM repasses_periodo)
      - (SELECT total FROM despesas_fixas)
      - (SELECT total FROM despesas_nao_operacionais)
  ) INTO resultado;

  RETURN resultado;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER STABLE;


-- ── ATUALIZAR mv_dre_custos_mensais: excluir 'excluida' ─────────

-- Materialized views não suportam CREATE OR REPLACE — precisa recriar.
DROP MATERIALIZED VIEW IF EXISTS mv_dre_custos_mensais;

CREATE MATERIALIZED VIEW mv_dre_custos_mensais AS
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
  WHERE d.status NOT IN ('rejeitada', 'excluida')
  GROUP BY 1
)
SELECT
  COALESCE(ia.mes, da.mes)                   AS mes,
  COALESCE(ia.total_impostos,            0)  AS total_impostos,
  COALESCE(da.despesas_fixas,            0)  AS despesas_fixas,
  COALESCE(da.despesas_nao_operacionais, 0)  AS despesas_nao_operacionais
FROM impostos_agg ia
FULL OUTER JOIN despesas_agg da ON da.mes = ia.mes;

CREATE UNIQUE INDEX idx_mv_dre_custos_pk ON mv_dre_custos_mensais(mes);

COMMENT ON MATERIALIZED VIEW mv_dre_custos_mensais IS
  'Pré-agrega impostos e despesas (fixas e não-operacionais) por mês.
   Exclui status rejeitada e excluida. Sprint 2 — atualizada.';


-- ── REFRESH após migration ────────────────────────────────────

SELECT refresh_mv_dre();
