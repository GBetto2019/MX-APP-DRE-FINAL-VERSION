-- =============================================================
-- MX Seguros — DRE-IA | Migration 0004: Seed inicial
-- Fase 1 | Seguradoras parceiras, ramos e equipes
-- Fonte: §1.1 do ESCOPO_DRE_IA_CORRETORA.md
-- =============================================================

-- ── RAMOS DE SEGURO ───────────────────────────────────────────

INSERT INTO ramos (codigo, nome) VALUES
  ('AUTO',       'Automóvel'),
  ('VIDA',       'Vida'),
  ('SAUDE',      'Saúde'),
  ('RE',         'Responsabilidade Empresarial'),
  ('BENEFICIOS', 'Benefícios'),
  ('RURAL',      'Rural'),
  ('AGRO',       'Agronegócio')
ON CONFLICT (codigo) DO NOTHING;

-- ── SEGURADORAS PARCEIRAS ─────────────────────────────────────
-- 25+ parceiras ativas da MX Seguros

INSERT INTO seguradoras (nome) VALUES
  ('Tokio Marine'),
  ('Sura'),
  ('HDI'),
  ('Allianz'),
  ('Sul América'),
  ('Bradesco Seguros'),
  ('Mapfre'),
  ('Prudential'),
  ('Zurich'),
  ('Chubb'),
  ('Sompo'),
  ('Yelum'),
  ('Suhai'),
  ('Axa'),
  ('Odonto Prev'),
  ('Darwin'),
  ('Ezze'),
  ('Fair Fax'),
  ('Kovr'),
  ('Metropole Life'),
  ('Alfa Seguros'),
  ('Akad'),
  ('Porto Seguro'),
  ('Liberty Seguros'),
  ('Itaú Seguros')
ON CONFLICT (nome) DO NOTHING;

-- ── CENTROS DE CUSTO (Equipes) ────────────────────────────────
-- Matriz e filial Águas de Lindoia como centro de custo

INSERT INTO equipes (nome, unidade) VALUES
  ('Equipe Comercial Matriz',     'matriz'),
  ('Equipe Agronegócio',          'agro'),
  ('Centro de Custo Águas de Lindoia', 'aguas_lindoia')
ON CONFLICT DO NOTHING;
