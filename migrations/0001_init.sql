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
