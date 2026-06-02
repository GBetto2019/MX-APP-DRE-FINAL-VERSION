-- ================================================================
-- 0016_migrar_categoria.sql
-- Task 3.4 — Migrar campo legado 'categoria' para 'tipo_lancamento_id'.
-- Safe para re-executar: só atualiza WHERE tipo_lancamento_id IS NULL.
-- ================================================================

-- Para cada despesa sem tipo_lancamento_id, associa o tipo_lancamento
-- correspondente pela categoria legada (prioriza o mais específico).
UPDATE despesas d
SET tipo_lancamento_id = (
    SELECT tl.id
    FROM tipos_lancamento tl
    WHERE tl.categoria = d.categoria::TEXT
      AND tl.natureza  = 'despesa'
      AND tl.ativo     = true
    ORDER BY
        -- Evita tipos genéricos (ex: "Outras Despesas Fixas")
        CASE tl.nome
            WHEN 'Outras Despesas Fixas'     THEN 2
            WHEN 'Outras Despesas Variáveis' THEN 2
            ELSE 1
        END,
        tl.criado_em
    LIMIT 1
)
WHERE d.tipo_lancamento_id IS NULL
  AND d.categoria IS NOT NULL;

-- Relatório pós-migração
DO $$
DECLARE
    v_total        INT;
    v_com_tipo     INT;
    v_sem_tipo     INT;
BEGIN
    SELECT COUNT(*) INTO v_total    FROM despesas;
    SELECT COUNT(*) INTO v_com_tipo FROM despesas WHERE tipo_lancamento_id IS NOT NULL;
    SELECT COUNT(*) INTO v_sem_tipo FROM despesas WHERE tipo_lancamento_id IS NULL;

    RAISE NOTICE 'Migração categoria→tipo_lancamento_id:';
    RAISE NOTICE '  Total despesas: %',       v_total;
    RAISE NOTICE '  Com tipo_lancamento_id: %', v_com_tipo;
    RAISE NOTICE '  Sem tipo_lancamento_id: %', v_sem_tipo;
    RAISE NOTICE '  (despesas sem categoria nem tipo ficam sem associacao)';
END;
$$;
