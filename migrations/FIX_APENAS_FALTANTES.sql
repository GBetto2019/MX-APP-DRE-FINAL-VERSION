-- ================================================================
-- FIX_APENAS_FALTANTES.sql
-- SQL cirúrgico: aplica SOMENTE o que está faltando no banco.
-- Seguro para rodar mesmo com bancos/tipos_lancamento já existindo.
-- Verificado em 01/06/2026.
-- ================================================================


-- ================================================================
-- PARTE 1: Colunas faltantes em DESPESAS
-- (banco_id e tipo_lancamento_id já existem — só status e auditoria)
-- ================================================================

-- status de aprovação
ALTER TABLE despesas
  ADD COLUMN IF NOT EXISTS status TEXT
    NOT NULL DEFAULT 'aprovada'
    CHECK (status IN ('pendente', 'aprovada', 'rejeitada', 'excluida'));

-- auditoria de quem criou/aprovou
ALTER TABLE despesas
  ADD COLUMN IF NOT EXISTS criado_por      UUID REFERENCES usuarios(id),
  ADD COLUMN IF NOT EXISTS aprovado_por    UUID REFERENCES usuarios(id),
  ADD COLUMN IF NOT EXISTS aprovado_em     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS rejeitado_motivo TEXT;

-- Ajustar despesas legadas (sem criado_por) para status aprovada
UPDATE despesas SET status = 'aprovada' WHERE status IS NULL;

-- Índice para queries por status
CREATE INDEX IF NOT EXISTS idx_despesas_status
  ON despesas(status) WHERE status != 'excluida';


-- ================================================================
-- PARTE 2: RLS completa de despesas
-- (Gestor vê operacionais, Comercial vê só as que criou)
-- ================================================================

DROP POLICY IF EXISTS despesas_gestor   ON despesas;
DROP POLICY IF EXISTS despesas_comercial ON despesas;

-- Gestor vê despesas operacionais (não pessoal/não-operacional)
CREATE POLICY despesas_gestor ON despesas
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'gestor'
    AND status != 'excluida'
    AND COALESCE(categoria::TEXT, '') NOT IN
        ('pessoal', 'nao_operacional', 'investimento_imobilizado')
    AND (
      tipo_lancamento_id IS NULL
      OR NOT EXISTS (
        SELECT 1 FROM tipos_lancamento tl
        WHERE tl.id = despesas.tipo_lancamento_id
          AND (tl.custo_tipo = 'nao_operacional' OR tl.categoria = 'pessoal')
      )
    )
  );

-- Comercial vê apenas despesas que ele mesmo criou
CREATE POLICY despesas_comercial ON despesas
  FOR SELECT TO authenticated
  USING (
    get_meu_role() = 'comercial'
    AND criado_por = auth.uid()
    AND status != 'excluida'
  );

-- INSERT para todos os roles autenticados
DROP POLICY IF EXISTS despesas_insert ON despesas;
CREATE POLICY despesas_insert ON despesas
  FOR INSERT TO authenticated
  WITH CHECK (true);

-- UPDATE só para admin e gestor
DROP POLICY IF EXISTS despesas_update ON despesas;
CREATE POLICY despesas_update ON despesas
  FOR UPDATE TO authenticated
  USING (get_meu_role() IN ('admin', 'gestor'));

-- DELETE só para admin (soft-delete via status='excluida')
DROP POLICY IF EXISTS despesas_delete ON despesas;
CREATE POLICY despesas_delete ON despesas
  FOR DELETE TO authenticated
  USING (get_meu_role() = 'admin');


-- ================================================================
-- PARTE 3: Fix atingimento_metas() — COUNT para numero_apolices
-- ================================================================

CREATE OR REPLACE FUNCTION atingimento_metas(p_competencia DATE)
RETURNS JSONB AS $$
  SELECT jsonb_agg(
    jsonb_build_object(
      'meta_id',     m.id,
      'escopo',      m.escopo,
      'escopo_id',   m.escopo_id,
      'metrica',     m.metrica,
      'valor_alvo',  m.valor_alvo,
      'valor_atual', COALESCE(realizado.total, 0),
      'percentual',  CASE
                       WHEN m.valor_alvo > 0
                       THEN ROUND((COALESCE(realizado.total, 0) / m.valor_alvo) * 100, 2)
                       ELSE 0
                     END,
      'atingida',    COALESCE(realizado.total, 0) >= m.valor_alvo
    )
  )
  FROM metas m
  LEFT JOIN LATERAL (
    SELECT
      CASE m.metrica
        WHEN 'numero_apolices'
          THEN COUNT(DISTINCT a.id)::NUMERIC
        ELSE
          COALESCE(SUM(c.valor), 0)
      END AS total
    FROM comissoes c
    JOIN apolices a ON a.id = c.apolice_id
    WHERE DATE_TRUNC('month', c.competencia) = DATE_TRUNC('month', p_competencia)
      AND CASE m.escopo
            WHEN 'global'   THEN true
            WHEN 'equipe'   THEN a.equipe_id  = m.escopo_id
            WHEN 'produtor' THEN a.produtor_id = m.escopo_id
            WHEN 'ramo'     THEN a.ramo_id     = m.escopo_id
            ELSE false
          END
  ) realizado ON true
  WHERE DATE_TRUNC('month', m.competencia) = DATE_TRUNC('month', p_competencia)
$$ LANGUAGE sql SECURITY INVOKER STABLE;


-- ================================================================
-- PARTE 4: Metas — remover escrita para Comercial
-- ================================================================

DROP POLICY IF EXISTS metas_update ON metas;
DROP POLICY IF EXISTS metas_delete ON metas;

CREATE POLICY metas_update ON metas
  FOR UPDATE TO authenticated
  USING (get_meu_role() IN ('admin', 'gestor'));

CREATE POLICY metas_delete ON metas
  FOR DELETE TO authenticated
  USING (get_meu_role() IN ('admin', 'gestor'));


-- ================================================================
-- PARTE 5: Atualizar dre_por_periodo() — excluir status 'excluida'
-- ================================================================

CREATE OR REPLACE FUNCTION dre_por_periodo(p_inicio DATE, p_fim DATE)
RETURNS JSONB AS $$
DECLARE resultado JSONB;
BEGIN
  WITH
  receita AS (
    SELECT COALESCE(SUM(c.valor), 0) AS total FROM comissoes c
    WHERE DATE_TRUNC('month', c.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio) AND DATE_TRUNC('month', p_fim)
  ),
  receitas_manuais AS (
    SELECT COALESCE(SUM(r.valor), 0) AS total FROM receitas_outras r
    WHERE DATE_TRUNC('month', r.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio) AND DATE_TRUNC('month', p_fim)
  ),
  estornos_periodo AS (
    SELECT COALESCE(SUM(e.valor), 0) AS total FROM estornos e
    WHERE DATE_TRUNC('month', e.competencia_estorno)
          BETWEEN DATE_TRUNC('month', p_inicio) AND DATE_TRUNC('month', p_fim)
  ),
  impostos_periodo AS (
    SELECT COALESCE(SUM(i.valor), 0) AS total FROM impostos i
    WHERE DATE_TRUNC('month', i.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio) AND DATE_TRUNC('month', p_fim)
  ),
  repasses_periodo AS (
    SELECT COALESCE(SUM(r.valor), 0) AS total FROM repasses r
    WHERE DATE_TRUNC('month', r.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio) AND DATE_TRUNC('month', p_fim)
      AND r.status != 'estornado'
  ),
  despesas_fixas AS (
    SELECT COALESCE(SUM(d.valor), 0) AS total FROM despesas d
    WHERE DATE_TRUNC('month', d.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio) AND DATE_TRUNC('month', p_fim)
      AND d.status NOT IN ('rejeitada', 'excluida')
      AND (
        (d.tipo_lancamento_id IS NULL AND d.categoria IN (
          'pessoal','comercial','administrativa_operacional','veiculos','terceiros','financeira'))
        OR (d.tipo_lancamento_id IS NOT NULL AND EXISTS (
          SELECT 1 FROM tipos_lancamento tl
          WHERE tl.id = d.tipo_lancamento_id AND tl.custo_tipo IN ('fixo','variavel')
        ))
      )
  ),
  despesas_nao_op AS (
    SELECT COALESCE(SUM(d.valor), 0) AS total FROM despesas d
    WHERE DATE_TRUNC('month', d.competencia)
          BETWEEN DATE_TRUNC('month', p_inicio) AND DATE_TRUNC('month', p_fim)
      AND d.status NOT IN ('rejeitada', 'excluida')
      AND (
        (d.tipo_lancamento_id IS NULL AND d.categoria IN ('nao_operacional','investimento_imobilizado'))
        OR (d.tipo_lancamento_id IS NOT NULL AND EXISTS (
          SELECT 1 FROM tipos_lancamento tl
          WHERE tl.id = d.tipo_lancamento_id AND tl.custo_tipo = 'nao_operacional'
        ))
      )
  )
  SELECT jsonb_build_object(
    'periodo',               jsonb_build_object('inicio', p_inicio, 'fim', p_fim),
    'receita_bruta',         (SELECT total FROM receita) + (SELECT total FROM receitas_manuais),
    'estornos',              (SELECT total FROM estornos_periodo),
    'impostos',              (SELECT total FROM impostos_periodo),
    'receita_liquida',       (SELECT total FROM receita) + (SELECT total FROM receitas_manuais)
                             - (SELECT total FROM estornos_periodo) - (SELECT total FROM impostos_periodo),
    'repasses_produtores',   (SELECT total FROM repasses_periodo),
    'margem_contribuicao',   (SELECT total FROM receita) + (SELECT total FROM receitas_manuais)
                             - (SELECT total FROM estornos_periodo) - (SELECT total FROM impostos_periodo)
                             - (SELECT total FROM repasses_periodo),
    'despesas_fixas',        (SELECT total FROM despesas_fixas),
    'ebitda',                (SELECT total FROM receita) + (SELECT total FROM receitas_manuais)
                             - (SELECT total FROM estornos_periodo) - (SELECT total FROM impostos_periodo)
                             - (SELECT total FROM repasses_periodo) - (SELECT total FROM despesas_fixas),
    'despesas_nao_operacionais', (SELECT total FROM despesas_nao_op),
    'resultado_liquido',     (SELECT total FROM receita) + (SELECT total FROM receitas_manuais)
                             - (SELECT total FROM estornos_periodo) - (SELECT total FROM impostos_periodo)
                             - (SELECT total FROM repasses_periodo) - (SELECT total FROM despesas_fixas)
                             - (SELECT total FROM despesas_nao_op)
  ) INTO resultado;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER STABLE;


-- ================================================================
-- PARTE 6: Tabela FECHAMENTOS (migration 0013)
-- ================================================================

CREATE TABLE IF NOT EXISTS fechamentos (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    competencia     DATE        NOT NULL,
    fechado_por     UUID        REFERENCES usuarios(id),
    fechado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    snapshot_dre    JSONB       NOT NULL,
    reaberto_por    UUID        REFERENCES usuarios(id),
    reaberto_em     TIMESTAMPTZ,
    reaberto_motivo TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fechamentos_competencia_ativo
    ON fechamentos(competencia) WHERE reaberto_em IS NULL;

CREATE INDEX IF NOT EXISTS idx_fechamentos_competencia
    ON fechamentos(competencia DESC);

ALTER TABLE fechamentos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS fechamentos_select ON fechamentos;
DROP POLICY IF EXISTS fechamentos_insert ON fechamentos;
DROP POLICY IF EXISTS fechamentos_update ON fechamentos;

CREATE POLICY fechamentos_select ON fechamentos
    FOR SELECT TO authenticated
    USING (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY fechamentos_insert ON fechamentos
    FOR INSERT TO authenticated
    WITH CHECK (get_meu_role() IN ('admin', 'contador'));

CREATE POLICY fechamentos_update ON fechamentos
    FOR UPDATE TO authenticated
    USING (get_meu_role() = 'admin');


-- ================================================================
-- PARTE 7: Tabelas CHAT_CONVERSAS e CHAT_MENSAGENS (migration 0014)
-- ================================================================

CREATE TABLE IF NOT EXISTS chat_conversas (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id    UUID        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    titulo        TEXT,
    criada_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
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

CREATE INDEX IF NOT EXISTS idx_chat_conversas_usuario
    ON chat_conversas(usuario_id, atualizada_em DESC);

CREATE INDEX IF NOT EXISTS idx_chat_mensagens_conversa
    ON chat_mensagens(conversa_id, criada_em);

ALTER TABLE chat_conversas ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_mensagens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS usuario_proprias_conversas ON chat_conversas;
DROP POLICY IF EXISTS usuario_proprias_mensagens ON chat_mensagens;

CREATE POLICY usuario_proprias_conversas ON chat_conversas
    FOR ALL USING (usuario_id = auth.uid())
    WITH CHECK (usuario_id = auth.uid());

CREATE POLICY usuario_proprias_mensagens ON chat_mensagens
    FOR ALL
    USING (conversa_id IN (SELECT id FROM chat_conversas WHERE usuario_id = auth.uid()))
    WITH CHECK (conversa_id IN (SELECT id FROM chat_conversas WHERE usuario_id = auth.uid()));

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

DROP TRIGGER IF EXISTS trg_limpar_conversas_antigas ON chat_conversas;
CREATE TRIGGER trg_limpar_conversas_antigas
    AFTER INSERT ON chat_conversas
    FOR EACH ROW EXECUTE FUNCTION limpar_conversas_antigas();


-- ================================================================
-- PARTE 8: AUDIT_LOG_ARCHIVE + função de rotação (migration 0015)
-- ================================================================

CREATE TABLE IF NOT EXISTS audit_log_archive (
    LIKE audit_log INCLUDING ALL
);

CREATE INDEX IF NOT EXISTS idx_audit_archive_criado_em
    ON audit_log_archive(criado_em DESC);

CREATE INDEX IF NOT EXISTS idx_audit_archive_usuario
    ON audit_log_archive(usuario_id, criado_em DESC);

ALTER TABLE audit_log_archive ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_archive_select ON audit_log_archive;
CREATE POLICY audit_archive_select ON audit_log_archive
    FOR SELECT TO authenticated
    USING (get_meu_role() IN ('admin', 'contador'));

CREATE OR REPLACE FUNCTION rotacionar_audit_log(p_dias INT DEFAULT 90)
RETURNS INT AS $$
DECLARE
    v_movidos INT;
    v_corte   TIMESTAMPTZ := now() - (p_dias || ' days')::INTERVAL;
BEGIN
    WITH movidos AS (
        DELETE FROM audit_log WHERE criado_em < v_corte RETURNING *
    )
    INSERT INTO audit_log_archive SELECT * FROM movidos;
    GET DIAGNOSTICS v_movidos = ROW_COUNT;
    RETURN v_movidos;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
