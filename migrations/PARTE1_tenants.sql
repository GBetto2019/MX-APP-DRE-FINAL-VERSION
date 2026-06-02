-- ================================================================
-- 0017_tenants.sql
-- Sprint 4 — Multi-Tenant: tabela tenants, planos e theming.
-- Sprint 5 — Theming dinâmico por tenant.
-- Sprint 6 — Limites por plano.
-- ================================================================

-- Enum de planos
CREATE TYPE plano_tipo AS ENUM ('basico', 'profissional', 'enterprise');

-- Tabela central de tenants
CREATE TABLE IF NOT EXISTS tenants (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nome         TEXT        NOT NULL,
    slug         TEXT        NOT NULL UNIQUE,   -- ex: 'mx-seguros', 'corretora-xpto'
    plano        plano_tipo  NOT NULL DEFAULT 'basico',
    ativo        BOOLEAN     NOT NULL DEFAULT true,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Sprint 5: Theming dinâmico
    logo_url         TEXT,
    cor_primaria     TEXT DEFAULT '#1F4E79',   -- azul MX por padrão
    cor_secundaria   TEXT DEFAULT '#2E86C1',
    nome_exibicao    TEXT,                      -- Nome para exibir no frontend
    setup_completo   BOOLEAN NOT NULL DEFAULT false,

    -- Sprint 6: Limites por plano
    max_usuarios     INT NOT NULL DEFAULT 5,
    max_msgs_ia_dia  INT NOT NULL DEFAULT 50,
    max_apolices     INT NOT NULL DEFAULT 1000,

    -- Billing
    stripe_customer_id  TEXT,
    asaas_customer_id   TEXT,
    trial_ate           DATE,
    bloqueado           BOOLEAN NOT NULL DEFAULT false,
    bloqueado_motivo    TEXT
);

CREATE INDEX IF NOT EXISTS idx_tenants_slug  ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_ativo ON tenants(ativo) WHERE ativo = true;

-- RLS habilitado; policies adicionadas em PARTE3 (após tenant_id existir em usuarios)
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;

-- ── Seed: MX Seguros (tenant inicial) ─────────────────────────
INSERT INTO tenants (
    nome, slug, plano, ativo,
    nome_exibicao, cor_primaria, cor_secundaria,
    setup_completo,
    max_usuarios, max_msgs_ia_dia, max_apolices
) VALUES (
    'MX Seguros', 'mx-seguros', 'profissional', true,
    'MX Seguros', '#1F4E79', '#2E86C1',
    true,
    50, 200, 10000
) ON CONFLICT (slug) DO NOTHING;

-- ── Enum super_admin no role de usuário ──────────────────────
-- Adiciona super_admin ao enum user_role existente
ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'super_admin';
