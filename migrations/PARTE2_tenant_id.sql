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
