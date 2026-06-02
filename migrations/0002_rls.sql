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
