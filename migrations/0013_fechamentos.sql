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
