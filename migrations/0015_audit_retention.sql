-- ══════════════════════════════════════════════════════════════
-- 0015_audit_retention.sql
-- Rotação automática do audit_log: move logs > 90 dias para archive.
-- Evita crescimento infinito da tabela.
-- ══════════════════════════════════════════════════════════════

-- Tabela de arquivo (mesma estrutura do audit_log)
CREATE TABLE IF NOT EXISTS audit_log_archive (
    LIKE audit_log INCLUDING ALL
);

-- Índice para consultas históricas por período
CREATE INDEX IF NOT EXISTS idx_audit_archive_criado_em
    ON audit_log_archive(criado_em DESC);

CREATE INDEX IF NOT EXISTS idx_audit_archive_usuario
    ON audit_log_archive(usuario_id, criado_em DESC);

-- RLS na archive (mesmas regras do audit_log)
ALTER TABLE audit_log_archive ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_archive_select ON audit_log_archive
    FOR SELECT TO authenticated
    USING (get_meu_role() IN ('admin', 'contador'));

-- Função de rotação: move logs > 90 dias para o archive
CREATE OR REPLACE FUNCTION rotacionar_audit_log(p_dias INT DEFAULT 90)
RETURNS INT AS $$
DECLARE
    v_movidos INT;
    v_corte   TIMESTAMPTZ := now() - (p_dias || ' days')::INTERVAL;
BEGIN
    -- Mover para archive
    WITH movidos AS (
        DELETE FROM audit_log
        WHERE criado_em < v_corte
        RETURNING *
    )
    INSERT INTO audit_log_archive SELECT * FROM movidos;

    GET DIAGNOSTICS v_movidos = ROW_COUNT;

    RETURN v_movidos;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION rotacionar_audit_log IS
    'Move logs de audit_log com mais de N dias para audit_log_archive.
     Chamar via pg_cron semanalmente: SELECT cron.schedule(...).
     Retorna o número de registros movidos.';

-- Instruções para agendar via pg_cron (rodar manualmente no SQL Editor):
-- SELECT cron.schedule(
--   'rotacao-audit-log-semanal',
--   '0 3 * * 0',   -- todo domingo às 03:00 UTC
--   'SELECT rotacionar_audit_log(90)'
-- );
