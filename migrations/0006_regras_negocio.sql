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
