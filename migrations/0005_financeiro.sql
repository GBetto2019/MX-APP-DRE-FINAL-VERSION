-- =============================================================
-- MX Seguros — DRE-IA | Migration 0005: Módulo Financeiro
-- Fase 7: Lançamentos manuais + parâmetros admin
-- =============================================================

-- ── BANCOS ────────────────────────────────────────────────────

CREATE TABLE bancos (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome      TEXT NOT NULL UNIQUE,
  ativo     BOOLEAN DEFAULT true,
  criado_em TIMESTAMPTZ DEFAULT now()
);

INSERT INTO bancos (nome) VALUES
  ('Itaú'),
  ('Santander'),
  ('Sicredi');

-- ── CENTROS DE CUSTO ──────────────────────────────────────────

CREATE TABLE centros_custo (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome      TEXT NOT NULL,
  codigo    TEXT NOT NULL UNIQUE,   -- 'matriz', 'aguas_lindoia'
  ativo     BOOLEAN DEFAULT true,
  criado_em TIMESTAMPTZ DEFAULT now()
);

INSERT INTO centros_custo (nome, codigo) VALUES
  ('Matriz',           'matriz'),
  ('Águas de Lindóia', 'aguas_lindoia');

-- ── TIPOS DE LANÇAMENTO (admin-configurável) ──────────────────

CREATE TABLE tipos_lancamento (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome        TEXT NOT NULL,
  natureza    TEXT NOT NULL CHECK (natureza IN ('despesa', 'receita')),
  -- categoria mapeia para despesa_categoria ENUM existente (backward compat)
  categoria   TEXT,
  -- custo_tipo classifica onde a linha cai no DRE
  custo_tipo  TEXT CHECK (custo_tipo IN ('fixo', 'variavel', 'nao_operacional')),
  ativo       BOOLEAN DEFAULT true,
  criado_em   TIMESTAMPTZ DEFAULT now()
);

-- Seeds: Despesas
INSERT INTO tipos_lancamento (nome, natureza, categoria, custo_tipo) VALUES
  ('Salário / Pró-labore',          'despesa', 'pessoal',                         'fixo'),
  ('Encargos Sociais (FGTS/INSS)',  'despesa', 'pessoal',                         'fixo'),
  ('Aluguel',                       'despesa', 'administrativa_operacional',       'fixo'),
  ('Sistemas / Software',           'despesa', 'administrativa_operacional',       'fixo'),
  ('Energia / Água / Telefone',     'despesa', 'administrativa_operacional',       'fixo'),
  ('Contabilidade / Jurídico',      'despesa', 'terceiros',                        'fixo'),
  ('Marketing / Publicidade',       'despesa', 'comercial',                        'variavel'),
  ('Comissão Comercial',            'despesa', 'comercial',                        'variavel'),
  ('Combustível / Veículos',        'despesa', 'veiculos',                         'variavel'),
  ('Tarifas Bancárias',             'despesa', 'financeira',                       'variavel'),
  ('IOF / Juros',                   'despesa', 'financeira',                       'variavel'),
  ('Multas / Encargos',             'despesa', 'nao_operacional',                  'nao_operacional'),
  ('Investimento / Imobilizado',    'despesa', 'investimento_imobilizado',          'nao_operacional'),
  ('Outras Despesas Fixas',         'despesa', 'administrativa_operacional',       'fixo'),
  ('Outras Despesas Variáveis',     'despesa', 'comercial',                        'variavel');

-- Seeds: Receitas
INSERT INTO tipos_lancamento (nome, natureza, categoria, custo_tipo) VALUES
  ('Receita de Serviço / Honorário', 'receita', NULL, NULL),
  ('Recuperação de Despesa',         'receita', NULL, NULL),
  ('Receita Financeira',             'receita', NULL, NULL),
  ('Outras Receitas',                'receita', NULL, NULL);

-- ── RECEITAS OUTRAS (lançamentos manuais não-comissão) ────────

CREATE TABLE receitas_outras (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tipo_lancamento_id  UUID REFERENCES tipos_lancamento(id),
  banco_id            UUID REFERENCES bancos(id),
  centro_custo        TEXT NOT NULL DEFAULT 'matriz',
  descricao           TEXT NOT NULL,
  valor               NUMERIC(14,2) NOT NULL CHECK (valor > 0),
  competencia         DATE NOT NULL,
  recebido_em         DATE,
  observacao          TEXT,
  criado_em           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_receitas_outras_competencia ON receitas_outras(competencia);
CREATE INDEX idx_receitas_outras_banco       ON receitas_outras(banco_id);

-- ── ALTERAR TABELA DESPESAS ────────────────────────────────────

-- Adicionar referências a banco e tipo (nullable — ETL existente não tem esses campos)
ALTER TABLE despesas
  ADD COLUMN banco_id           UUID REFERENCES bancos(id),
  ADD COLUMN tipo_lancamento_id UUID REFERENCES tipos_lancamento(id);

-- Remover CHECK constraint fixo: validação passa a ser pela tabela centros_custo
ALTER TABLE despesas
  DROP CONSTRAINT IF EXISTS despesas_centro_custo_check;

-- ── ATUALIZAR FUNÇÃO DRE: incluir receitas_outras ─────────────

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
      AND (
        -- Despesas legadas via ENUM
        (d.tipo_lancamento_id IS NULL AND d.categoria IN (
          'pessoal', 'comercial', 'administrativa_operacional',
          'veiculos', 'terceiros', 'financeira'
        ))
        OR
        -- Despesas novas via tipos_lancamento
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

-- ── RLS — BANCOS (todos leem; só admin cria/edita) ─────────────

ALTER TABLE bancos ENABLE ROW LEVEL SECURITY;

CREATE POLICY bancos_select ON bancos
  FOR SELECT TO authenticated
  USING (true);

CREATE POLICY bancos_insert ON bancos
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() = 'admin');

CREATE POLICY bancos_update ON bancos
  FOR UPDATE TO authenticated
  USING (get_meu_role() = 'admin');

-- ── RLS — CENTROS DE CUSTO (todos leem; só admin cria/edita) ──

ALTER TABLE centros_custo ENABLE ROW LEVEL SECURITY;

CREATE POLICY centros_custo_select ON centros_custo
  FOR SELECT TO authenticated
  USING (true);

CREATE POLICY centros_custo_insert ON centros_custo
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() = 'admin');

CREATE POLICY centros_custo_update ON centros_custo
  FOR UPDATE TO authenticated
  USING (get_meu_role() = 'admin');

-- ── RLS — TIPOS DE LANÇAMENTO (todos leem; só admin cria/edita) ─

ALTER TABLE tipos_lancamento ENABLE ROW LEVEL SECURITY;

CREATE POLICY tipos_lancamento_select ON tipos_lancamento
  FOR SELECT TO authenticated
  USING (true);

CREATE POLICY tipos_lancamento_insert ON tipos_lancamento
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() = 'admin');

CREATE POLICY tipos_lancamento_update ON tipos_lancamento
  FOR UPDATE TO authenticated
  USING (get_meu_role() = 'admin');

-- ── RLS — RECEITAS OUTRAS (admin + contador leem/criam; só admin edita) ─

ALTER TABLE receitas_outras ENABLE ROW LEVEL SECURITY;

CREATE POLICY receitas_outras_select ON receitas_outras
  FOR SELECT TO authenticated
  USING (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY receitas_outras_insert ON receitas_outras
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY receitas_outras_update ON receitas_outras
  FOR UPDATE TO authenticated
  USING (get_meu_role() = 'admin');

CREATE POLICY receitas_outras_delete ON receitas_outras
  FOR DELETE TO authenticated
  USING (get_meu_role() = 'admin');
