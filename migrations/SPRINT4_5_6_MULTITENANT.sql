-- SPRINT 4+5+6: Multi-tenant, Theming e Billing
-- Aplique no SQL Editor: https://supabase.com/dashboard/project/jrqmntvmtukmhlmnukgn/sql/new

-- ===== 0017_tenants.sql =====
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

-- RLS: super_admin vê tudo; outros veem só o próprio tenant
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_proprio ON tenants
    FOR SELECT TO authenticated
    USING (
        id IN (SELECT tenant_id FROM usuarios WHERE id = auth.uid())
        OR get_meu_role() = 'super_admin'
    );

CREATE POLICY tenant_super_admin_write ON tenants
    FOR ALL TO authenticated
    USING (get_meu_role() = 'super_admin')
    WITH CHECK (get_meu_role() = 'super_admin');

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


-- ===== 0018_add_tenant_id.sql =====
-- ================================================================
-- 0018_add_tenant_id.sql
-- Sprint 4: Adiciona tenant_id em todas as 20 tabelas operacionais.
-- Estratégia segura:
--   1. ADD COLUMN nullable (não quebra queries existentes)
--   2. UPDATE com o tenant MX Seguros para dados legados
--   3. Índices compostos com tenant_id (performance multi-tenant)
-- NÃO adicionamos NOT NULL constraint aqui — apenas após validação.
-- ================================================================

DO $$
DECLARE v_tenant_id UUID;
BEGIN
    SELECT id INTO v_tenant_id FROM tenants WHERE slug = 'mx-seguros';
    IF v_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Tenant mx-seguros não encontrado. Execute 0017_tenants.sql primeiro.';
    END IF;

    -- ── Adicionar tenant_id em cada tabela ─────────────────────

    ALTER TABLE equipes       ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE produtores     ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE usuarios       ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE seguradoras    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE ramos          ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE clientes       ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE apolices       ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE comissoes      ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE repasses       ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE estornos       ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE despesas       ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE impostos       ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE metas          ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE fechamentos    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE audit_log      ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE chat_conversas ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE bancos         ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE centros_custo  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE tipos_lancamento ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
    ALTER TABLE receitas_outras  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);

    -- ── Popular todos os dados legados com MX Seguros ──────────

    UPDATE equipes       SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE produtores     SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE usuarios       SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE seguradoras    SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE ramos          SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE clientes       SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE apolices       SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE comissoes      SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE repasses       SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE estornos       SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE despesas       SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE impostos       SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE metas          SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE fechamentos    SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE audit_log      SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE chat_conversas SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE bancos         SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE centros_custo  SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE tipos_lancamento SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;
    UPDATE receitas_outras  SET tenant_id = v_tenant_id WHERE tenant_id IS NULL;

    RAISE NOTICE 'tenant_id populado com sucesso para tenant: %', v_tenant_id;
END;
$$;

-- ── Índices compostos com tenant_id ────────────────────────────
-- Garantem que queries filtradas por tenant usem index scan

CREATE INDEX IF NOT EXISTS idx_usuarios_tenant       ON usuarios(tenant_id);
CREATE INDEX IF NOT EXISTS idx_equipes_tenant        ON equipes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_apolices_tenant       ON apolices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_comissoes_tenant      ON comissoes(tenant_id, competencia);
CREATE INDEX IF NOT EXISTS idx_despesas_tenant       ON despesas(tenant_id, competencia);
CREATE INDEX IF NOT EXISTS idx_repasses_tenant       ON repasses(tenant_id, competencia);
CREATE INDEX IF NOT EXISTS idx_estornos_tenant       ON estornos(tenant_id);
CREATE INDEX IF NOT EXISTS idx_fechamentos_tenant    ON fechamentos(tenant_id, competencia);
CREATE INDEX IF NOT EXISTS idx_chat_conversas_tenant ON chat_conversas(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant      ON audit_log(tenant_id, criado_em DESC);


-- ===== 0019_rls_multitenant.sql =====
-- ================================================================
-- 0019_rls_multitenant.sql
-- Sprint 4: Atualiza TODAS as policies RLS para isolamento por tenant.
-- Princípio: tenant_id do usuário logado define o escopo de dados.
-- Super_admin vê todos os tenants.
-- ================================================================

-- ── Helper: tenant do usuário logado ─────────────────────────
CREATE OR REPLACE FUNCTION get_meu_tenant()
RETURNS UUID AS $$
    SELECT tenant_id FROM usuarios WHERE id = auth.uid()
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ── Helper: verificar se é super_admin ───────────────────────
CREATE OR REPLACE FUNCTION is_super_admin()
RETURNS BOOLEAN AS $$
    SELECT role = 'super_admin' FROM usuarios WHERE id = auth.uid()
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ── Macro helper: condição de tenant ─────────────────────────
-- Combina: tenant_id correto OU super_admin
-- Uso: AND _tenant_ok(tabela.tenant_id)
CREATE OR REPLACE FUNCTION _tenant_ok(p_tenant_id UUID)
RETURNS BOOLEAN AS $$
    SELECT p_tenant_id = get_meu_tenant() OR is_super_admin()
$$ LANGUAGE sql SECURITY DEFINER STABLE;


-- ══════════════════════════════════════════════════════════════
-- ATUALIZAR POLICIES (DROP + CREATE com tenant_id)
-- ══════════════════════════════════════════════════════════════

-- ── USUARIOS ─────────────────────────────────────────────────
DROP POLICY IF EXISTS usuarios_select ON usuarios;
CREATE POLICY usuarios_select ON usuarios
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND (id = auth.uid() OR get_meu_role() IN ('admin', 'contador', 'super_admin'))
    );

DROP POLICY IF EXISTS usuarios_insert ON usuarios;
CREATE POLICY usuarios_insert ON usuarios
    FOR INSERT TO authenticated
    WITH CHECK (
        tenant_id = get_meu_tenant()
        AND get_meu_role() IN ('admin', 'super_admin')
    );

DROP POLICY IF EXISTS usuarios_update ON usuarios;
CREATE POLICY usuarios_update ON usuarios
    FOR UPDATE TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND get_meu_role() IN ('admin', 'super_admin')
    );

-- ── EQUIPES ──────────────────────────────────────────────────
DROP POLICY IF EXISTS equipes_select ON equipes;
CREATE POLICY equipes_select ON equipes
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id));

DROP POLICY IF EXISTS equipes_insert ON equipes;
CREATE POLICY equipes_insert ON equipes
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'super_admin'));

DROP POLICY IF EXISTS equipes_update ON equipes;
CREATE POLICY equipes_update ON equipes
    FOR UPDATE TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'super_admin'));

-- ── PRODUTORES ───────────────────────────────────────────────
DROP POLICY IF EXISTS produtores_select ON produtores;
CREATE POLICY produtores_select ON produtores
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND (
            get_meu_role() IN ('admin', 'gestor', 'contador', 'super_admin')
            OR id = get_meu_produtor()
        )
    );

DROP POLICY IF EXISTS produtores_insert ON produtores;
CREATE POLICY produtores_insert ON produtores
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'super_admin'));

-- ── SEGURADORAS ──────────────────────────────────────────────
DROP POLICY IF EXISTS seguradoras_select ON seguradoras;
CREATE POLICY seguradoras_select ON seguradoras
    FOR SELECT TO authenticated USING (_tenant_ok(tenant_id));

DROP POLICY IF EXISTS seguradoras_insert ON seguradoras;
CREATE POLICY seguradoras_insert ON seguradoras
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'super_admin'));

-- ── RAMOS ────────────────────────────────────────────────────
DROP POLICY IF EXISTS ramos_select ON ramos;
CREATE POLICY ramos_select ON ramos
    FOR SELECT TO authenticated USING (_tenant_ok(tenant_id));

DROP POLICY IF EXISTS ramos_insert ON ramos;
CREATE POLICY ramos_insert ON ramos
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'super_admin'));

-- ── CLIENTES ─────────────────────────────────────────────────
DROP POLICY IF EXISTS clientes_select ON clientes;
CREATE POLICY clientes_select ON clientes
    FOR SELECT TO authenticated USING (_tenant_ok(tenant_id));

DROP POLICY IF EXISTS clientes_insert ON clientes;
CREATE POLICY clientes_insert ON clientes
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant());

-- ── APOLICES ─────────────────────────────────────────────────
DROP POLICY IF EXISTS apolices_select ON apolices;
CREATE POLICY apolices_select ON apolices
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND (
            get_meu_role() IN ('admin', 'contador', 'super_admin')
            OR (get_meu_role() = 'gestor'    AND equipe_id   = get_minha_equipe())
            OR (get_meu_role() = 'comercial' AND produtor_id = get_meu_produtor())
        )
    );

DROP POLICY IF EXISTS apolices_insert ON apolices;
CREATE POLICY apolices_insert ON apolices
    FOR INSERT TO authenticated
    WITH CHECK (
        tenant_id = get_meu_tenant()
        AND get_meu_role() IN ('admin', 'gestor', 'comercial', 'super_admin')
    );

DROP POLICY IF EXISTS apolices_update ON apolices;
CREATE POLICY apolices_update ON apolices
    FOR UPDATE TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND (
            get_meu_role() IN ('admin', 'super_admin')
            OR (get_meu_role() = 'gestor' AND equipe_id = get_minha_equipe())
        )
    );

-- ── COMISSOES ────────────────────────────────────────────────
DROP POLICY IF EXISTS comissoes_admin ON comissoes;
CREATE POLICY comissoes_admin ON comissoes
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

DROP POLICY IF EXISTS comissoes_gestor ON comissoes;
CREATE POLICY comissoes_gestor ON comissoes
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND get_meu_role() = 'gestor'
        AND EXISTS (SELECT 1 FROM apolices a WHERE a.id = comissoes.apolice_id AND a.equipe_id = get_minha_equipe())
    );

DROP POLICY IF EXISTS comissoes_comercial ON comissoes;
CREATE POLICY comissoes_comercial ON comissoes
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND get_meu_role() = 'comercial'
        AND EXISTS (SELECT 1 FROM apolices a WHERE a.id = comissoes.apolice_id AND a.produtor_id = get_meu_produtor())
    );

DROP POLICY IF EXISTS comissoes_insert ON comissoes;
CREATE POLICY comissoes_insert ON comissoes
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'gestor', 'super_admin'));

-- ── REPASSES ─────────────────────────────────────────────────
DROP POLICY IF EXISTS repasses_admin ON repasses;
CREATE POLICY repasses_admin ON repasses
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

DROP POLICY IF EXISTS repasses_gestor ON repasses;
CREATE POLICY repasses_gestor ON repasses
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND get_meu_role() = 'gestor'
        AND EXISTS (SELECT 1 FROM produtores p WHERE p.id = repasses.produtor_id AND p.equipe_id = get_minha_equipe())
    );

DROP POLICY IF EXISTS repasses_comercial ON repasses;
CREATE POLICY repasses_comercial ON repasses
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() = 'comercial' AND produtor_id = get_meu_produtor());

DROP POLICY IF EXISTS repasses_insert ON repasses;
CREATE POLICY repasses_insert ON repasses
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'gestor', 'super_admin'));

DROP POLICY IF EXISTS repasses_update ON repasses;
CREATE POLICY repasses_update ON repasses
    FOR UPDATE TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'gestor', 'super_admin'));

-- ── ESTORNOS ─────────────────────────────────────────────────
DROP POLICY IF EXISTS estornos_admin ON estornos;
CREATE POLICY estornos_admin ON estornos
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

DROP POLICY IF EXISTS estornos_gestor ON estornos;
CREATE POLICY estornos_gestor ON estornos
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND get_meu_role() = 'gestor'
        AND EXISTS (SELECT 1 FROM apolices a WHERE a.id = estornos.apolice_id AND a.equipe_id = get_minha_equipe())
    );

DROP POLICY IF EXISTS estornos_comercial ON estornos;
CREATE POLICY estornos_comercial ON estornos
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND get_meu_role() = 'comercial'
        AND EXISTS (SELECT 1 FROM apolices a WHERE a.id = estornos.apolice_id AND a.produtor_id = get_meu_produtor())
    );

DROP POLICY IF EXISTS estornos_insert ON estornos;
CREATE POLICY estornos_insert ON estornos
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'gestor', 'super_admin'));

-- ── DESPESAS ─────────────────────────────────────────────────
DROP POLICY IF EXISTS despesas_select ON despesas;
CREATE POLICY despesas_select ON despesas
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

DROP POLICY IF EXISTS despesas_gestor ON despesas;
CREATE POLICY despesas_gestor ON despesas
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND get_meu_role() = 'gestor'
        AND status != 'excluida'
        AND COALESCE(categoria::TEXT, '') NOT IN ('pessoal', 'nao_operacional', 'investimento_imobilizado')
        AND (tipo_lancamento_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM tipos_lancamento tl
            WHERE tl.id = despesas.tipo_lancamento_id
              AND (tl.custo_tipo = 'nao_operacional' OR tl.categoria = 'pessoal')
        ))
    );

DROP POLICY IF EXISTS despesas_comercial ON despesas;
CREATE POLICY despesas_comercial ON despesas
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() = 'comercial' AND criado_por = auth.uid() AND status != 'excluida');

DROP POLICY IF EXISTS despesas_insert ON despesas;
CREATE POLICY despesas_insert ON despesas
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant());

DROP POLICY IF EXISTS despesas_update ON despesas;
CREATE POLICY despesas_update ON despesas
    FOR UPDATE TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'gestor', 'super_admin'));

DROP POLICY IF EXISTS despesas_delete ON despesas;
CREATE POLICY despesas_delete ON despesas
    FOR DELETE TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'super_admin'));

-- ── IMPOSTOS ─────────────────────────────────────────────────
DROP POLICY IF EXISTS impostos_select ON impostos;
CREATE POLICY impostos_select ON impostos
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

DROP POLICY IF EXISTS impostos_insert ON impostos;
CREATE POLICY impostos_insert ON impostos
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

-- ── METAS ────────────────────────────────────────────────────
DROP POLICY IF EXISTS metas_admin ON metas;
CREATE POLICY metas_admin ON metas
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

DROP POLICY IF EXISTS metas_gestor ON metas;
CREATE POLICY metas_gestor ON metas
    FOR SELECT TO authenticated
    USING (
        _tenant_ok(tenant_id)
        AND get_meu_role() = 'gestor'
        AND (
            escopo = 'global'
            OR (escopo = 'equipe'   AND escopo_id = get_minha_equipe())
            OR (escopo = 'produtor' AND EXISTS (SELECT 1 FROM produtores p WHERE p.id = metas.escopo_id AND p.equipe_id = get_minha_equipe()))
            OR escopo = 'ramo'
        )
    );

DROP POLICY IF EXISTS metas_comercial ON metas;
CREATE POLICY metas_comercial ON metas
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() = 'comercial' AND escopo = 'produtor' AND escopo_id = get_meu_produtor());

DROP POLICY IF EXISTS metas_insert ON metas;
CREATE POLICY metas_insert ON metas
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'gestor', 'super_admin'));

DROP POLICY IF EXISTS metas_update ON metas;
CREATE POLICY metas_update ON metas
    FOR UPDATE TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'gestor', 'super_admin'));

DROP POLICY IF EXISTS metas_delete ON metas;
CREATE POLICY metas_delete ON metas
    FOR DELETE TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'gestor', 'super_admin'));

-- ── FECHAMENTOS ──────────────────────────────────────────────
DROP POLICY IF EXISTS fechamentos_select ON fechamentos;
CREATE POLICY fechamentos_select ON fechamentos
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

DROP POLICY IF EXISTS fechamentos_insert ON fechamentos;
CREATE POLICY fechamentos_insert ON fechamentos
    FOR INSERT TO authenticated
    WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

DROP POLICY IF EXISTS fechamentos_update ON fechamentos;
CREATE POLICY fechamentos_update ON fechamentos
    FOR UPDATE TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'super_admin'));

-- ── AUDIT_LOG ────────────────────────────────────────────────
DROP POLICY IF EXISTS audit_select ON audit_log;
CREATE POLICY audit_select ON audit_log
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'contador', 'super_admin'));

DROP POLICY IF EXISTS audit_insert ON audit_log;
CREATE POLICY audit_insert ON audit_log
    FOR INSERT TO authenticated WITH CHECK (true);

-- ── CHAT_CONVERSAS / CHAT_MENSAGENS ──────────────────────────
DROP POLICY IF EXISTS usuario_proprias_conversas ON chat_conversas;
CREATE POLICY usuario_proprias_conversas ON chat_conversas
    FOR ALL
    USING (_tenant_ok(tenant_id) AND usuario_id = auth.uid())
    WITH CHECK (_tenant_ok(tenant_id) AND usuario_id = auth.uid());

DROP POLICY IF EXISTS usuario_proprias_mensagens ON chat_mensagens;
CREATE POLICY usuario_proprias_mensagens ON chat_mensagens
    FOR ALL
    USING (conversa_id IN (SELECT id FROM chat_conversas WHERE usuario_id = auth.uid()))
    WITH CHECK (conversa_id IN (SELECT id FROM chat_conversas WHERE usuario_id = auth.uid()));

-- ── BANCOS / CENTROS_CUSTO / TIPOS_LANCAMENTO / RECEITAS_OUTRAS ─
DROP POLICY IF EXISTS bancos_select ON bancos;
CREATE POLICY bancos_select ON bancos FOR SELECT TO authenticated USING (_tenant_ok(tenant_id));
DROP POLICY IF EXISTS bancos_insert ON bancos;
CREATE POLICY bancos_insert ON bancos FOR INSERT TO authenticated WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'super_admin'));
DROP POLICY IF EXISTS bancos_update ON bancos;
CREATE POLICY bancos_update ON bancos FOR UPDATE TO authenticated USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'super_admin'));

DROP POLICY IF EXISTS centros_custo_select ON centros_custo;
CREATE POLICY centros_custo_select ON centros_custo FOR SELECT TO authenticated USING (_tenant_ok(tenant_id));
DROP POLICY IF EXISTS centros_custo_insert ON centros_custo;
CREATE POLICY centros_custo_insert ON centros_custo FOR INSERT TO authenticated WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'super_admin'));
DROP POLICY IF EXISTS centros_custo_update ON centros_custo;
CREATE POLICY centros_custo_update ON centros_custo FOR UPDATE TO authenticated USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'super_admin'));

DROP POLICY IF EXISTS tipos_lancamento_select ON tipos_lancamento;
CREATE POLICY tipos_lancamento_select ON tipos_lancamento FOR SELECT TO authenticated USING (_tenant_ok(tenant_id));
DROP POLICY IF EXISTS tipos_lancamento_insert ON tipos_lancamento;
CREATE POLICY tipos_lancamento_insert ON tipos_lancamento FOR INSERT TO authenticated WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'super_admin'));
DROP POLICY IF EXISTS tipos_lancamento_update ON tipos_lancamento;
CREATE POLICY tipos_lancamento_update ON tipos_lancamento FOR UPDATE TO authenticated USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'super_admin'));

DROP POLICY IF EXISTS receitas_outras_select ON receitas_outras;
CREATE POLICY receitas_outras_select ON receitas_outras FOR SELECT TO authenticated USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'contador', 'super_admin'));
DROP POLICY IF EXISTS receitas_outras_insert ON receitas_outras;
CREATE POLICY receitas_outras_insert ON receitas_outras FOR INSERT TO authenticated WITH CHECK (tenant_id = get_meu_tenant() AND get_meu_role() IN ('admin', 'contador', 'super_admin'));
DROP POLICY IF EXISTS receitas_outras_update ON receitas_outras;
CREATE POLICY receitas_outras_update ON receitas_outras FOR UPDATE TO authenticated USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'super_admin'));
DROP POLICY IF EXISTS receitas_outras_delete ON receitas_outras;
CREATE POLICY receitas_outras_delete ON receitas_outras FOR DELETE TO authenticated USING (_tenant_ok(tenant_id) AND get_meu_role() IN ('admin', 'super_admin'));


