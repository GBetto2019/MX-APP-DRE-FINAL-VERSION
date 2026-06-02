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
