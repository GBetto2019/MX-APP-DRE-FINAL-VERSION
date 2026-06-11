-- 0023_permissions.sql
-- Adiciona coluna permissions (JSONB) à tabela usuarios
-- NULL = usa permissões padrão da role (compatibilidade com usuários existentes)

ALTER TABLE usuarios
  ADD COLUMN IF NOT EXISTS permissions JSONB DEFAULT NULL;

COMMENT ON COLUMN usuarios.permissions IS
  'Permissões granulares por tela e ação. NULL = padrão da role. Formato: {"tela": {"acao": bool}}';
