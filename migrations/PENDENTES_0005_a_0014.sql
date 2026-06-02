-- MIGRATIONS PENDENTES: 0005 a 0014
-- Aplique no SQL Editor do Supabase

-- ===== 0005_financeiro.sql =====
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


-- ===== 0006_regras_negocio.sql =====
-- =============================================================
-- MX Seguros — DRE-IA | Migration 0006: Regras de Negócio
-- Fase 8: Aprovação de Despesas, CRUD Metas, CRUD Usuários
-- =============================================================

-- ── 1. DESPESAS: novos campos de ciclo de vida ────────────────

ALTER TABLE despesas
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'aprovada'
    CHECK (status IN ('pendente', 'aprovada', 'rejeitada')),
  ADD COLUMN IF NOT EXISTS criado_por UUID REFERENCES usuarios(id),
  ADD COLUMN IF NOT EXISTS aprovado_por UUID REFERENCES usuarios(id),
  ADD COLUMN IF NOT EXISTS aprovado_em TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS rejeitado_motivo TEXT;

-- Despesas existentes ficam aprovadas (retroativo)
UPDATE despesas SET status = 'aprovada' WHERE status IS NULL;

-- ── 2. RLS — DESPESAS: Gestor vê todas; Comercial vê as suas ──

-- Remove políticas antigas
DROP POLICY IF EXISTS despesas_select ON despesas;
DROP POLICY IF EXISTS despesas_insert ON despesas;
DROP POLICY IF EXISTS despesas_update ON despesas;
DROP POLICY IF EXISTS despesas_delete ON despesas;

-- Admin e Contador: veem tudo (igual a antes)
CREATE POLICY despesas_admin_contador ON despesas
  FOR SELECT TO authenticated
  USING (get_meu_role() IN ('admin', 'contador'));

-- Gestor: vê todas as despesas (financeiro da equipe)
CREATE POLICY despesas_gestor ON despesas
  FOR SELECT TO authenticated
  USING (get_meu_role() = 'gestor');

-- Comercial: vê apenas as que ele mesmo criou
CREATE POLICY despesas_comercial ON despesas
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'comercial'
    AND criado_por = auth.uid()
  );

-- Quem pode inserir: admin, contador, gestor e comercial
CREATE POLICY despesas_insert ON despesas
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'contador', 'gestor', 'comercial'));

-- Quem pode atualizar (incluindo aprovar/rejeitar): admin e gestor
CREATE POLICY despesas_update ON despesas
  FOR UPDATE TO authenticated
  USING (get_meu_role() IN ('admin', 'gestor'));

-- Quem pode deletar: apenas admin
CREATE POLICY despesas_delete ON despesas
  FOR DELETE TO authenticated
  USING (get_meu_role() = 'admin');

-- ── 3. RLS — METAS: bloquear Contador; add delete; comercial edita/deleta própria ──

-- Remove políticas antigas
DROP POLICY IF EXISTS metas_admin ON metas;
DROP POLICY IF EXISTS metas_delete ON metas;
DROP POLICY IF EXISTS metas_update ON metas;

-- Admin: vê todas as metas (Contador fica só com SELECT via política separada abaixo)
CREATE POLICY metas_admin ON metas
  FOR SELECT TO authenticated
  USING (get_meu_role() = 'admin');

-- Contador: somente leitura de todas as metas
CREATE POLICY metas_contador ON metas
  FOR SELECT TO authenticated
  USING (get_meu_role() = 'contador');

-- Update: admin e gestor (qualquer meta); comercial (só a própria)
CREATE POLICY metas_update ON metas
  FOR UPDATE TO authenticated
  USING (
    get_meu_role() IN ('admin', 'gestor')
    OR (
      get_meu_role() = 'comercial'
      AND escopo = 'produtor'
      AND escopo_id = get_meu_produtor()
    )
  );

-- Delete: admin e gestor (qualquer meta); comercial (só a própria)
CREATE POLICY metas_delete ON metas
  FOR DELETE TO authenticated
  USING (
    get_meu_role() IN ('admin', 'gestor')
    OR (
      get_meu_role() = 'comercial'
      AND escopo = 'produtor'
      AND escopo_id = get_meu_produtor()
    )
  );

-- ── 4. RLS — USUARIOS: Gestor pode criar e atualizar ──────────

-- Remove políticas antigas
DROP POLICY IF EXISTS usuarios_select ON usuarios;
DROP POLICY IF EXISTS usuarios_insert ON usuarios;
DROP POLICY IF EXISTS usuarios_update ON usuarios;

-- Leitura: próprio, admin, gestor e contador
CREATE POLICY usuarios_select ON usuarios
  FOR SELECT TO authenticated
  USING (
    id = auth.uid()
    OR get_meu_role() IN ('admin', 'gestor', 'contador')
  );

-- Inserção: admin e gestor
CREATE POLICY usuarios_insert ON usuarios
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'gestor'));

-- Atualização: admin e gestor
CREATE POLICY usuarios_update ON usuarios
  FOR UPDATE TO authenticated
  USING (get_meu_role() IN ('admin', 'gestor'));

-- ── 5. ÍNDICES para os novos campos ───────────────────────────

CREATE INDEX IF NOT EXISTS idx_despesas_status     ON despesas(status);
CREATE INDEX IF NOT EXISTS idx_despesas_criado_por ON despesas(criado_por);


-- ===== 0010_indices.sql =====
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


-- ===== 0011_materialized_view.sql =====
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


-- ===== 0012_sprint2_seguranca.sql =====
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


-- ===== 0013_fechamentos.sql =====
-- =============================================================
-- MX Seguros — DRE-IA | Migration 0013: Fechamentos Mensais
-- =============================================================
-- Tabela de fechamentos mensais: cada registro representa um
-- período "congelado" com snapshot completo do DRE.
-- Reabertura não apaga o registro — mantém histórico de auditoria.
-- Partial unique index garante no máximo UM fechamento ativo
-- (não reaberto) por mês.
-- =============================================================

CREATE TABLE IF NOT EXISTS fechamentos (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    competencia     DATE        NOT NULL,   -- sempre o primeiro dia do mês
    fechado_por     UUID        REFERENCES usuarios(id),
    fechado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    snapshot_dre    JSONB       NOT NULL,   -- DRE completo no momento do fechamento
    reaberto_por    UUID        REFERENCES usuarios(id),
    reaberto_em     TIMESTAMPTZ,
    reaberto_motivo TEXT
);

-- Garante no máximo um fechamento ATIVO por mês.
-- Fechamentos reabertos (reaberto_em IS NOT NULL) ficam no histórico.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fechamentos_competencia_ativo
    ON fechamentos(competencia)
    WHERE reaberto_em IS NULL;

CREATE INDEX IF NOT EXISTS idx_fechamentos_competencia
    ON fechamentos(competencia DESC);

-- ── RLS ───────────────────────────────────────────────────────

ALTER TABLE fechamentos ENABLE ROW LEVEL SECURITY;

-- Admin e Contador: leitura completa
CREATE POLICY fechamentos_select ON fechamentos
    FOR SELECT TO authenticated
    USING (get_meu_role() IN ('admin', 'contador'));

-- Admin e Contador: podem criar fechamentos
CREATE POLICY fechamentos_insert ON fechamentos
    FOR INSERT TO authenticated
    WITH CHECK (get_meu_role() IN ('admin', 'contador'));

-- Apenas Admin: pode reabrir (UPDATE)
CREATE POLICY fechamentos_update ON fechamentos
    FOR UPDATE TO authenticated
    USING (get_meu_role() = 'admin');

-- Sem DELETE: fechamentos são imutáveis (só reabrir)


-- ===== 0014_chat_historico.sql =====
-- ══════════════════════════════════════════════════════════════
-- 0014_chat_historico.sql
-- Persistência de histórico de conversas do chat com IA.
-- RLS: cada usuário vê apenas suas próprias conversas.
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS chat_conversas (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id   UUID        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    titulo       TEXT,
    criada_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizada_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_mensagens (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversa_id  UUID        NOT NULL REFERENCES chat_conversas(id) ON DELETE CASCADE,
    role         TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    conteudo     TEXT        NOT NULL,
    tool_calls   JSONB,
    criada_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_chat_conversas_usuario
    ON chat_conversas(usuario_id, atualizada_em DESC);

CREATE INDEX IF NOT EXISTS idx_chat_mensagens_conversa
    ON chat_mensagens(conversa_id, criada_em);

-- RLS
ALTER TABLE chat_conversas ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_mensagens ENABLE ROW LEVEL SECURITY;

-- Conversa: usuário vê apenas as suas
CREATE POLICY usuario_proprias_conversas ON chat_conversas
    FOR ALL
    USING (usuario_id = auth.uid())
    WITH CHECK (usuario_id = auth.uid());

-- Mensagens: usuário vê apenas de suas conversas
CREATE POLICY usuario_proprias_mensagens ON chat_mensagens
    FOR ALL
    USING (
        conversa_id IN (
            SELECT id FROM chat_conversas WHERE usuario_id = auth.uid()
        )
    )
    WITH CHECK (
        conversa_id IN (
            SELECT id FROM chat_conversas WHERE usuario_id = auth.uid()
        )
    );

-- Limpeza automática: manter apenas as 50 conversas mais recentes por usuário
-- (chamado pelo trigger abaixo)
CREATE OR REPLACE FUNCTION limpar_conversas_antigas()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM chat_conversas
    WHERE id IN (
        SELECT id FROM chat_conversas
        WHERE usuario_id = NEW.usuario_id
        ORDER BY atualizada_em DESC
        OFFSET 50
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER trg_limpar_conversas_antigas
    AFTER INSERT ON chat_conversas
    FOR EACH ROW
    EXECUTE FUNCTION limpar_conversas_antigas();


