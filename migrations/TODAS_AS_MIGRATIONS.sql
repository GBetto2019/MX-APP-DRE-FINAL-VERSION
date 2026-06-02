-- MX Seguros DRE-IA | Todas as migrations combinadas
-- Gerado automaticamente | Cole no SQL Editor do Supabase

-- =============================================================
-- 0001_init.sql
-- =============================================================
-- =============================================================
-- MX Seguros — DRE-IA | Migration 0001: Schema inicial
-- Fase 1 | Todas as tabelas do sistema
-- =============================================================

-- ── ENUMS ────────────────────────────────────────────────────

CREATE TYPE user_role AS ENUM ('admin', 'gestor', 'comercial', 'contador');

CREATE TYPE despesa_categoria AS ENUM (
  'pessoal',
  'comercial',
  'administrativa_operacional',
  'veiculos',
  'terceiros',
  'financeira',
  'nao_operacional',
  'investimento_imobilizado'
);

-- ── TABELAS DE CADASTRO ───────────────────────────────────────

CREATE TABLE equipes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome        TEXT NOT NULL,
  unidade     TEXT NOT NULL CHECK (unidade IN ('matriz', 'aguas_lindoia', 'agro')),
  gestor_id   UUID,  -- FK adicionada depois para evitar dependência circular
  ativo       BOOLEAN DEFAULT true,
  criado_em   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE produtores (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome        TEXT NOT NULL,
  documento   TEXT,
  tipo        TEXT CHECK (tipo IN ('interno', 'externo', 'sub_corretor')),
  equipe_id   UUID REFERENCES equipes(id),
  ativo       BOOLEAN DEFAULT true,
  criado_em   TIMESTAMPTZ DEFAULT now()
);

-- Usuários espelha auth.users do Supabase
CREATE TABLE usuarios (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  nome        TEXT NOT NULL,
  email       TEXT UNIQUE NOT NULL,
  role        user_role NOT NULL DEFAULT 'comercial',
  equipe_id   UUID REFERENCES equipes(id),
  produtor_id UUID REFERENCES produtores(id),
  ativo       BOOLEAN DEFAULT true,
  criado_em   TIMESTAMPTZ DEFAULT now()
);

-- Agora adiciona FK de equipes.gestor_id -> usuarios
ALTER TABLE equipes
  ADD CONSTRAINT fk_equipes_gestor
  FOREIGN KEY (gestor_id) REFERENCES usuarios(id);

CREATE TABLE seguradoras (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome      TEXT NOT NULL UNIQUE,
  cnpj      TEXT,
  ativo     BOOLEAN DEFAULT true,
  criado_em TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE ramos (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo    TEXT UNIQUE NOT NULL,  -- 'AUTO', 'VIDA', 'SAUDE', 'RE', 'BENEFICIOS', 'RURAL', 'AGRO'
  nome      TEXT NOT NULL,
  criado_em TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE clientes (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome      TEXT NOT NULL,
  documento TEXT,
  tipo      TEXT CHECK (tipo IN ('pf', 'pj')),
  criado_em TIMESTAMPTZ DEFAULT now()
);

-- ── OPERAÇÃO ──────────────────────────────────────────────────

CREATE TABLE apolices (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  numero          TEXT NOT NULL,
  seguradora_id   UUID NOT NULL REFERENCES seguradoras(id),
  ramo_id         UUID NOT NULL REFERENCES ramos(id),
  cliente_id      UUID NOT NULL REFERENCES clientes(id),
  produtor_id     UUID NOT NULL REFERENCES produtores(id),
  equipe_id       UUID REFERENCES equipes(id),
  premio_total    NUMERIC(14,2) NOT NULL,
  inicio_vigencia DATE NOT NULL,
  fim_vigencia    DATE NOT NULL,
  status          TEXT CHECK (status IN ('ativa', 'cancelada', 'renovada')) DEFAULT 'ativa',
  emitida_em      DATE NOT NULL,   -- competência da receita (regime de competência)
  criado_em       TIMESTAMPTZ DEFAULT now(),
  UNIQUE (numero, seguradora_id)
);

CREATE TABLE comissoes (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  apolice_id   UUID NOT NULL REFERENCES apolices(id),
  tipo         TEXT CHECK (tipo IN ('comissao_padrao', 'agenciamento', 'override_rappel')),
  valor        NUMERIC(14,2) NOT NULL,
  percentual   NUMERIC(6,4),
  competencia  DATE NOT NULL,   -- mês/ano de reconhecimento (regime de competência)
  recebida_em  DATE,            -- quando entrou no banco (regime de caixa)
  criado_em    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE repasses (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  comissao_id  UUID NOT NULL REFERENCES comissoes(id),
  produtor_id  UUID NOT NULL REFERENCES produtores(id),
  valor        NUMERIC(14,2) NOT NULL,
  percentual   NUMERIC(6,4),
  competencia  DATE NOT NULL,
  pago_em      DATE,
  status       TEXT CHECK (status IN ('previsto', 'pago', 'estornado')) DEFAULT 'previsto',
  criado_em    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE estornos (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  apolice_id           UUID NOT NULL REFERENCES apolices(id),
  comissao_original_id UUID REFERENCES comissoes(id),
  valor                NUMERIC(14,2) NOT NULL,
  motivo               TEXT,
  competencia_original DATE NOT NULL,  -- período da comissão estornada (para análise)
  competencia_estorno  DATE NOT NULL,  -- período em que o estorno IMPACTA o DRE
  criado_em            TIMESTAMPTZ DEFAULT now()
);

-- ── DESPESAS ──────────────────────────────────────────────────

CREATE TABLE despesas (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  categoria       despesa_categoria NOT NULL,
  subcategoria    TEXT NOT NULL,   -- 'salario', 'aluguel', 'sistema_crm', etc.
  descricao       TEXT NOT NULL,
  valor           NUMERIC(14,2) NOT NULL,
  competencia     DATE NOT NULL,
  paga_em         DATE,
  centro_custo    TEXT NOT NULL DEFAULT 'matriz'
                    CHECK (centro_custo IN ('matriz', 'aguas_lindoia')),
  recorrente      BOOLEAN DEFAULT false,
  parcela_atual   INT,
  parcela_total   INT,
  criado_em       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE impostos (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tipo          TEXT CHECK (tipo IN ('simples_nacional', 'iss', 'pis', 'cofins', 'irpj', 'csll')),
  competencia   DATE NOT NULL,
  base_calculo  NUMERIC(14,2) NOT NULL,
  aliquota      NUMERIC(6,4) NOT NULL,
  valor         NUMERIC(14,2) NOT NULL,
  pago_em       DATE,
  criado_em     TIMESTAMPTZ DEFAULT now()
);

-- ── METAS ────────────────────────────────────────────────────

CREATE TABLE metas (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  escopo      TEXT CHECK (escopo IN ('global', 'equipe', 'produtor', 'ramo')),
  escopo_id   UUID,   -- aponta para equipe/produtor/ramo conforme escopo
  competencia DATE NOT NULL,
  valor_alvo  NUMERIC(14,2) NOT NULL,
  metrica     TEXT CHECK (metrica IN ('receita_bruta', 'comissao_liquida', 'numero_apolices')),
  criado_em   TIMESTAMPTZ DEFAULT now()
);

-- ── AUDITORIA ─────────────────────────────────────────────────

CREATE TABLE audit_log (
  id          BIGSERIAL PRIMARY KEY,
  usuario_id  UUID REFERENCES usuarios(id),
  acao        TEXT NOT NULL,   -- 'consulta_dre', 'chat_ia', 'login', 'export'
  detalhes    JSONB,
  ip          TEXT,
  criado_em   TIMESTAMPTZ DEFAULT now()
);

-- ── ÍNDICES PARA PERFORMANCE ──────────────────────────────────

-- apolices: buscas por período são frequentes
CREATE INDEX idx_apolices_emitida_em    ON apolices(emitida_em);
CREATE INDEX idx_apolices_produtor      ON apolices(produtor_id);
CREATE INDEX idx_apolices_equipe        ON apolices(equipe_id);
CREATE INDEX idx_apolices_seguradora    ON apolices(seguradora_id);

-- comissoes: filtros por competência e apólice
CREATE INDEX idx_comissoes_competencia  ON comissoes(competencia);
CREATE INDEX idx_comissoes_apolice      ON comissoes(apolice_id);

-- despesas: filtros por competência e centro de custo
CREATE INDEX idx_despesas_competencia   ON despesas(competencia);
CREATE INDEX idx_despesas_centro_custo  ON despesas(centro_custo);

-- estornos: filtros por competência de impacto
CREATE INDEX idx_estornos_competencia   ON estornos(competencia_estorno);

-- repasses: filtros por competência e status
CREATE INDEX idx_repasses_competencia   ON repasses(competencia);
CREATE INDEX idx_repasses_status        ON repasses(status);

-- audit_log: buscas por usuário e data
CREATE INDEX idx_audit_usuario          ON audit_log(usuario_id);
CREATE INDEX idx_audit_criado_em        ON audit_log(criado_em);

-- =============================================================
-- 0002_rls.sql
-- =============================================================
-- =============================================================
-- MX Seguros — DRE-IA | Migration 0002: Row-Level Security
-- Fase 1 | Políticas de acesso por perfil
-- Matriz de permissões: ver §4.5 do ESCOPO_DRE_IA_CORRETORA.md
-- =============================================================

-- ── HELPER: função para pegar o role do usuário logado ────────

CREATE OR REPLACE FUNCTION get_meu_role()
RETURNS user_role AS $$
  SELECT role FROM usuarios WHERE id = auth.uid()
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION get_minha_equipe()
RETURNS UUID AS $$
  SELECT equipe_id FROM usuarios WHERE id = auth.uid()
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION get_meu_produtor()
RETURNS UUID AS $$
  SELECT produtor_id FROM usuarios WHERE id = auth.uid()
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ── USUARIOS ──────────────────────────────────────────────────

ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;

-- Usuário vê apenas o próprio perfil; admin vê todos
CREATE POLICY usuarios_select ON usuarios
  FOR SELECT TO authenticated
  USING (
    id = auth.uid()
    OR get_meu_role() = 'admin'
    OR get_meu_role() = 'contador'
  );

-- Somente admin pode inserir/atualizar usuários
CREATE POLICY usuarios_insert ON usuarios
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() = 'admin');

CREATE POLICY usuarios_update ON usuarios
  FOR UPDATE TO authenticated
  USING (get_meu_role() = 'admin');

-- ── EQUIPES ───────────────────────────────────────────────────

ALTER TABLE equipes ENABLE ROW LEVEL SECURITY;

-- Todos os autenticados veem as equipes (não é dado sensível)
CREATE POLICY equipes_select ON equipes
  FOR SELECT TO authenticated USING (true);

CREATE POLICY equipes_insert ON equipes
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() = 'admin');

CREATE POLICY equipes_update ON equipes
  FOR UPDATE TO authenticated
  USING (get_meu_role() = 'admin');

-- ── PRODUTORES ────────────────────────────────────────────────

ALTER TABLE produtores ENABLE ROW LEVEL SECURITY;

-- Admin e Gestor veem todos; Comercial vê apenas o próprio
CREATE POLICY produtores_select ON produtores
  FOR SELECT TO authenticated
  USING (
    get_meu_role() IN ('admin', 'gestor', 'contador')
    OR id = get_meu_produtor()
  );

CREATE POLICY produtores_insert ON produtores
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() = 'admin');

-- ── SEGURADORAS ───────────────────────────────────────────────

ALTER TABLE seguradoras ENABLE ROW LEVEL SECURITY;

-- Todos veem (cadastro público interno)
CREATE POLICY seguradoras_select ON seguradoras
  FOR SELECT TO authenticated USING (true);

CREATE POLICY seguradoras_insert ON seguradoras
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() = 'admin');

-- ── RAMOS ─────────────────────────────────────────────────────

ALTER TABLE ramos ENABLE ROW LEVEL SECURITY;

CREATE POLICY ramos_select ON ramos
  FOR SELECT TO authenticated USING (true);

CREATE POLICY ramos_insert ON ramos
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() = 'admin');

-- ── CLIENTES ──────────────────────────────────────────────────

ALTER TABLE clientes ENABLE ROW LEVEL SECURITY;

-- Todos veem clientes (necessário para operação)
CREATE POLICY clientes_select ON clientes
  FOR SELECT TO authenticated USING (true);

CREATE POLICY clientes_insert ON clientes
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'gestor', 'comercial'));

-- ── APOLICES ──────────────────────────────────────────────────

ALTER TABLE apolices ENABLE ROW LEVEL SECURITY;

-- Admin/Contador: vê todas
-- Gestor: vê da sua equipe
-- Comercial: vê apenas as suas
CREATE POLICY apolices_select ON apolices
  FOR SELECT TO authenticated
  USING (
    get_meu_role() IN ('admin', 'contador')
    OR (get_meu_role() = 'gestor'   AND equipe_id = get_minha_equipe())
    OR (get_meu_role() = 'comercial' AND produtor_id = get_meu_produtor())
  );

CREATE POLICY apolices_insert ON apolices
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'gestor', 'comercial'));

CREATE POLICY apolices_update ON apolices
  FOR UPDATE TO authenticated
  USING (
    get_meu_role() = 'admin'
    OR (get_meu_role() = 'gestor' AND equipe_id = get_minha_equipe())
  );

-- ── COMISSOES ─────────────────────────────────────────────────
-- Dado sensível: controle rigoroso

ALTER TABLE comissoes ENABLE ROW LEVEL SECURITY;

-- Admin/Contador: todas
CREATE POLICY comissoes_admin ON comissoes
  FOR SELECT TO authenticated
  USING (get_meu_role() IN ('admin', 'contador'));

-- Gestor: comissões das apólices da sua equipe
CREATE POLICY comissoes_gestor ON comissoes
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'gestor'
    AND EXISTS (
      SELECT 1 FROM apolices a
      WHERE a.id = comissoes.apolice_id
        AND a.equipe_id = get_minha_equipe()
    )
  );

-- Comercial: somente as próprias apólices
CREATE POLICY comissoes_comercial ON comissoes
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'comercial'
    AND EXISTS (
      SELECT 1 FROM apolices a
      WHERE a.id = comissoes.apolice_id
        AND a.produtor_id = get_meu_produtor()
    )
  );

CREATE POLICY comissoes_insert ON comissoes
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'gestor'));

-- ── REPASSES ──────────────────────────────────────────────────
-- Sensível: produtor vê apenas os próprios

ALTER TABLE repasses ENABLE ROW LEVEL SECURITY;

CREATE POLICY repasses_admin ON repasses
  FOR SELECT TO authenticated
  USING (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY repasses_gestor ON repasses
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'gestor'
    AND EXISTS (
      SELECT 1 FROM produtores p
      WHERE p.id = repasses.produtor_id
        AND p.equipe_id = get_minha_equipe()
    )
  );

CREATE POLICY repasses_comercial ON repasses
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'comercial'
    AND produtor_id = get_meu_produtor()
  );

CREATE POLICY repasses_insert ON repasses
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'gestor'));

CREATE POLICY repasses_update ON repasses
  FOR UPDATE TO authenticated
  USING (get_meu_role() IN ('admin', 'gestor'));

-- ── ESTORNOS ──────────────────────────────────────────────────

ALTER TABLE estornos ENABLE ROW LEVEL SECURITY;

CREATE POLICY estornos_admin ON estornos
  FOR SELECT TO authenticated
  USING (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY estornos_gestor ON estornos
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'gestor'
    AND EXISTS (
      SELECT 1 FROM apolices a
      WHERE a.id = estornos.apolice_id
        AND a.equipe_id = get_minha_equipe()
    )
  );

CREATE POLICY estornos_comercial ON estornos
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'comercial'
    AND EXISTS (
      SELECT 1 FROM apolices a
      WHERE a.id = estornos.apolice_id
        AND a.produtor_id = get_meu_produtor()
    )
  );

CREATE POLICY estornos_insert ON estornos
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'gestor'));

-- ── DESPESAS ──────────────────────────────────────────────────
-- Altamente sensível: somente Admin e Contador

ALTER TABLE despesas ENABLE ROW LEVEL SECURITY;

CREATE POLICY despesas_select ON despesas
  FOR SELECT TO authenticated
  USING (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY despesas_insert ON despesas
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY despesas_update ON despesas
  FOR UPDATE TO authenticated
  USING (get_meu_role() = 'admin');

-- ── IMPOSTOS ──────────────────────────────────────────────────

ALTER TABLE impostos ENABLE ROW LEVEL SECURITY;

CREATE POLICY impostos_select ON impostos
  FOR SELECT TO authenticated
  USING (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY impostos_insert ON impostos
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'contador'));

-- ── METAS ─────────────────────────────────────────────────────

ALTER TABLE metas ENABLE ROW LEVEL SECURITY;

-- Admin vê e altera tudo
-- Gestor vê metas globais + da sua equipe + dos seus produtores
-- Comercial vê apenas metas individuais próprias
CREATE POLICY metas_admin ON metas
  FOR SELECT TO authenticated
  USING (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY metas_gestor ON metas
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'gestor'
    AND (
      escopo = 'global'
      OR (escopo = 'equipe'    AND escopo_id = get_minha_equipe())
      OR (escopo = 'produtor'  AND EXISTS (
          SELECT 1 FROM produtores p
          WHERE p.id = metas.escopo_id AND p.equipe_id = get_minha_equipe()
      ))
      OR escopo = 'ramo'
    )
  );

CREATE POLICY metas_comercial ON metas
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'comercial'
    AND escopo = 'produtor'
    AND escopo_id = get_meu_produtor()
  );

CREATE POLICY metas_insert ON metas
  FOR INSERT TO authenticated
  WITH CHECK (get_meu_role() IN ('admin', 'gestor'));

CREATE POLICY metas_update ON metas
  FOR UPDATE TO authenticated
  USING (get_meu_role() IN ('admin', 'gestor'));

-- ── AUDIT_LOG ─────────────────────────────────────────────────
-- Append-only: somente Admin e Contador leem; todos inserem (sistema insere)

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_select ON audit_log
  FOR SELECT TO authenticated
  USING (get_meu_role() IN ('admin', 'contador'));

-- Qualquer usuário autenticado pode inserir (o sistema insere automaticamente)
CREATE POLICY audit_insert ON audit_log
  FOR INSERT TO authenticated
  WITH CHECK (true);

-- Ninguém pode deletar ou atualizar audit_log (append-only)

-- =============================================================
-- 0003_functions.sql
-- =============================================================
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

-- =============================================================
-- 0004_seed.sql
-- =============================================================
-- =============================================================
-- MX Seguros — DRE-IA | Migration 0004: Seed inicial
-- Fase 1 | Seguradoras parceiras, ramos e equipes
-- Fonte: §1.1 do ESCOPO_DRE_IA_CORRETORA.md
-- =============================================================

-- ── RAMOS DE SEGURO ───────────────────────────────────────────

INSERT INTO ramos (codigo, nome) VALUES
  ('AUTO',       'Automóvel'),
  ('VIDA',       'Vida'),
  ('SAUDE',      'Saúde'),
  ('RE',         'Responsabilidade Empresarial'),
  ('BENEFICIOS', 'Benefícios'),
  ('RURAL',      'Rural'),
  ('AGRO',       'Agronegócio')
ON CONFLICT (codigo) DO NOTHING;

-- ── SEGURADORAS PARCEIRAS ─────────────────────────────────────
-- 25+ parceiras ativas da MX Seguros

INSERT INTO seguradoras (nome) VALUES
  ('Tokio Marine'),
  ('Sura'),
  ('HDI'),
  ('Allianz'),
  ('Sul América'),
  ('Bradesco Seguros'),
  ('Mapfre'),
  ('Prudential'),
  ('Zurich'),
  ('Chubb'),
  ('Sompo'),
  ('Yelum'),
  ('Suhai'),
  ('Axa'),
  ('Odonto Prev'),
  ('Darwin'),
  ('Ezze'),
  ('Fair Fax'),
  ('Kovr'),
  ('Metropole Life'),
  ('Alfa Seguros'),
  ('Akad'),
  ('Porto Seguro'),
  ('Liberty Seguros'),
  ('Itaú Seguros')
ON CONFLICT (nome) DO NOTHING;

-- ── CENTROS DE CUSTO (Equipes) ────────────────────────────────
-- Matriz e filial Águas de Lindoia como centro de custo

INSERT INTO equipes (nome, unidade) VALUES
  ('Equipe Comercial Matriz',     'matriz'),
  ('Equipe Agronegócio',          'agro'),
  ('Centro de Custo Águas de Lindoia', 'aguas_lindoia')
ON CONFLICT DO NOTHING;

