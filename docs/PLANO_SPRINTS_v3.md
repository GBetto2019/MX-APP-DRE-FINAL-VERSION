# Plano de Sprints — MX DRE-IA v3
**Gerado em:** 01/06/2026  
**Base:** SDD_MX_DRE_IA_v3.docx comparado ao código atual  
**Convenção de commit:** `pytest` passa 100% → commit → próxima task

---

## Diagnóstico Geral: O que está pronto vs. o que falta

### Fundação (Fases 1–4 do ESCOPO original)
| Fase | Status | Evidência |
|---|---|---|
| Fase 1 — Schema + RLS + Auth | ✅ Completo | migrations/0001–0004, test_rls.py |
| Fase 2 — ETL balancete | ✅ Completo (scripts) | etl/import_balancete.py, categorizacao.py, MIGRACAO_2026.md |
| Fase 3 — API FastAPI | ✅ Completo | 9 routers, 30+ endpoints, test_api.py (87 testes) |
| Fase 4 — IA / Chat | ✅ Completo | orchestrator.py, tools.py, streaming SSE, test_adversarial.py |

**Conclusão:** o núcleo do sistema está implementado e testado. O que falta são os itens do SDD v3 — gaps de segurança, UX, regras de negócio incompletas e infraestrutura.

---

## Status detalhado por Sprint (SDD v3)

### Sprint 0 — Dívida Técnica e UX

| Task | Descrição | Status | Observação |
|---|---|---|---|
| 0.1 | Rate limiting (slowapi) | ❌ Falta | Nenhum middleware de throttle encontrado |
| 0.2 | CORS restritivo + security headers | ❌ Falta | main.py provavelmente usa `*` |
| 0.3 | Loading states + ErrorBoundary (frontend) | ❌ Falta | Frontend Next.js está no estado default |
| 0.4 | Validação PeriodoPicker (≤ 12 meses) | ❌ Falta | Backend não rejeita períodos longos |
| 0.5 | Validação Pydantic completa | ⚠️ Parcial | schemas.py tem modelos mas sem ge/le/max_length |
| 0.6 | Export PDF/Excel do DRE | ❌ Falta | Contador não consegue exportar |
| 0.7 | Persistência do histórico de chat | ❌ Falta | Sem tabela chat_conversas/chat_mensagens |
| 0.8 | Tela de gestão de usuários (frontend) | ❌ Falta | Backend tem usuario_service.py, falta frontend |

### Sprint 1 — Performance

| Task | Descrição | Status | Observação |
|---|---|---|---|
| 1.1 | Índices compostos | ✅ Feito | migration/0010_indices.sql |
| 1.2 | Migrar para asyncpg (eliminar PostgREST) | ⚠️ Parcial | asyncpg mencionado como opção, PostgREST ainda é padrão |
| 1.3 | Endpoint GET /dashboard (agregado) | ❌ Falta | Frontend faz chamadas sequenciais |
| 1.4 | Promise.all no frontend | ❌ Falta | Depende de 1.3 |
| 1.5 | Cache de role (TTLCache 60s) | ✅ Feito | auth.py com TTL 60s |

### Sprint 2 — Segurança de Dados

| Task | Descrição | Status | Observação |
|---|---|---|---|
| 2.1 | RLS estornos por produtor | ❌ Bug conhecido | Comercial vê estornos de outros |
| 2.2 | Despesas sensíveis ocultas para Gestor | ❌ Bug conhecido | Gestor vê pessoal/não-operacional |
| 2.3 | Soft-delete em despesas | ❌ Falta | DELETE físico sem auditoria |
| 2.4 | Metas readonly para Comercial | ❌ Bug conhecido | Comercial pode alterar valor_alvo |
| 2.5 | Despesas de não-admin entram como `pendente` | ⚠️ Parcial | Campos existem, service não força |

### Sprint 3 — Regras de Negócio + ETL

| Task | Descrição | Status | Observação |
|---|---|---|---|
| 3.1 | Fechamento mensal (travar período) | ✅ Feito | migration/0013, fechamento_service.py |
| 3.2 | DRE híbrido snapshot/real-time | ❌ Falta | DRE sempre calculado em tempo real |
| 3.3 | Fix `atingimento_metas` (COUNT vs SUM) | ❌ Bug ativo | Documentado como bug em services |
| 3.4 | Migrar `categoria` legado → `tipo_lancamento_id` | ⚠️ Parcial | Dois campos coexistem sem migração |
| 3.5 | ETL via API (upload + preview + confirmar) | ⚠️ Parcial | Scripts ETL existem, sem endpoint/frontend |

### Sprint 4 — Multi-Tenant

| Task | Descrição | Status |
|---|---|---|
| 4.1–4.5 | Tabela tenants, tenant_id, RLS, middleware, super_admin | ❌ Falta completo |

### Sprint 5 — Onboarding e Theming

| Task | Descrição | Status |
|---|---|---|
| 5.1–5.3 | Theming dinâmico, setup wizard, wildcard DNS | ❌ Falta completo |

### Sprint 6 — Billing e Limites

| Task | Descrição | Status |
|---|---|---|
| 6.1–6.3 | Validação de limites, Stripe/Asaas, dashboard super_admin | ❌ Falta completo |

### Sprint 7 — Observabilidade e DevOps

| Task | Descrição | Status | Observação |
|---|---|---|---|
| 7.1 | Logging estruturado (structlog) | ❌ Falta | Sem logging formatado |
| 7.2 | Health check detalhado | ✅ Feito | GET /health existe |
| 7.3 | CI/CD GitHub Actions | ❌ Falta | Sem .github/workflows/ |
| 7.4 | Rotação de audit_log (90 dias) | ❌ Falta | Tabela cresce infinito |

---

## Plano de Execução por Sprint

> **Regra de ouro:** antes de cada `git commit`, todos os testes do sprint devem passar.  
> Sequência: implementar → testar → commit → próxima task.

---

## Sprint 0 — Dívida Técnica e UX
**Branch:** `fix/sprint-0-divida-tecnica`  
**Duração estimada:** 1–2 semanas  
**Prioridade:** MÁXIMA — afeta a operação atual

### Task 0.1 — Rate Limiting
**Arquivos:** `app/middleware/rate_limit.py` (novo), `app/main.py`

```python
# app/middleware/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
# /chat          → 10/min
# /dre, /dashboard → 30/min
# demais         → 60/min
```

**Testes antes do commit:**
```bash
# Instalar
pip install slowapi

# Teste manual: 11 requests rápidos para /chat → 11º retorna 429
# Teste automatizado:
pytest tests/test_rate_limit.py -v
```

**Testes a criar (`tests/test_rate_limit.py`):**
- `test_chat_limite_10_por_minuto` → 11º request retorna 429
- `test_dre_limite_30_por_minuto`
- `test_outros_endpoints_60_por_minuto`

**Commit:** `feat(segurança): rate limiting via slowapi — /chat 10/min, /dre 30/min`

---

### Task 0.2 — CORS Restritivo + Security Headers
**Arquivos:** `app/main.py`

```python
# Substituir allow_origins=['*'] por:
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv('FRONTEND_URL', 'http://localhost:3000'),
    ],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
    allow_headers=['Authorization', 'Content-Type'],
)

# Middleware de headers:
@app.middleware('http')
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response
```

**Testes antes do commit:**
```bash
pytest tests/test_security_headers.py -v
```

**Testes a criar:**
- `test_cors_origem_nao_autorizada_rejeitada` → origin `http://malicious.com` recebe erro CORS
- `test_security_header_x_frame_options` → header `DENY` presente
- `test_security_header_hsts` → header `Strict-Transport-Security` presente
- `test_security_header_nosniff` → header `X-Content-Type-Options: nosniff` presente

**Commit:** `feat(segurança): CORS restritivo e security headers (HSTS, CSP, X-Frame)`

---

### Task 0.3 — Loading States + ErrorBoundary (Frontend)
**Arquivos:** `frontend/components/LoadingSkeleton.tsx` (novo), `frontend/components/ErrorBoundary.tsx` (novo), todas as Views

**Testes antes do commit:**
```bash
cd frontend && pnpm test
```

**Testes a criar (Vitest/Jest):**
- `test_loading_skeleton_variantes` → variant='table'|'card'|'chart' renderiza
- `test_error_boundary_captura_erro` → erro de API mostra mensagem amigável
- `test_dre_view_mostra_skeleton_durante_loading`
- `test_nenhuma_tela_branca_sem_api` → mock API offline, nenhum componente quebra

**Commit:** `feat(frontend): LoadingSkeleton e ErrorBoundary em todas as Views`

---

### Task 0.4 — Validação PeriodoPicker (≤ 12 meses)
**Arquivos:** `frontend/components/PeriodoPicker.tsx`, `app/routers/dre.py`, todos routers com período

```python
# app/routers/dre.py
from datetime import date
from fastapi import Query, HTTPException

@router.get('/dre')
async def get_dre(
    inicio: date = Query(...),
    fim: date = Query(...)
):
    if (fim - inicio).days > 365:
        raise HTTPException(400, 'Período máximo permitido: 12 meses')
    if fim < inicio:
        raise HTTPException(400, 'Data inicial deve ser anterior à final')
```

**Testes antes do commit:**
```bash
pytest tests/test_api.py::test_periodo_invalido -v
pytest tests/test_api.py::test_periodo_maximo -v
```

**Testes a criar:**
- `test_periodo_superior_12_meses_retorna_400`
- `test_data_fim_antes_inicio_retorna_400`
- `test_periodo_valido_12_meses_aceito`

**Commit:** `fix: validar intervalo máximo de 12 meses em todos os endpoints de período`

---

### Task 0.5 — Validação Pydantic Completa
**Arquivo:** `app/models/schemas.py`

```python
from pydantic import BaseModel, field_validator
from decimal import Decimal
from datetime import date

class DespesaCreate(BaseModel):
    valor: Decimal = Field(ge=0, le=99_999_999.99)
    descricao: str = Field(min_length=3, max_length=500)
    competencia: date
    percentual: Decimal | None = Field(default=None, ge=0, le=100)

    @field_validator('competencia')
    @classmethod
    def competencia_nao_futuro(cls, v: date) -> date:
        from datetime import date as d
        limite = d.today().replace(day=1)
        from dateutil.relativedelta import relativedelta
        limite += relativedelta(months=2)
        if v > limite:
            raise ValueError('Competência não pode ser mais de 2 meses no futuro')
        return v
```

**Testes antes do commit:**
```bash
pytest tests/test_api.py -k "validacao" -v
```

**Testes a criar:**
- `test_despesa_valor_negativo_retorna_422`
- `test_despesa_descricao_50k_chars_retorna_422`
- `test_despesa_competencia_futuro_distante_retorna_422`
- `test_percentual_acima_100_retorna_422`

**Commit:** `fix(schemas): validações completas (valor>=0, max_length, competencia futura)`

---

### Task 0.6 — Export DRE PDF e Excel
**Arquivos:** `app/services/export_service.py` (novo), `app/routers/exports.py` (novo)

```python
# app/services/export_service.py
from io import BytesIO
import openpyxl
from reportlab.platypus import SimpleDocTemplate, Table

async def gerar_dre_excel(dre_data: dict, periodo: dict) -> BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'DRE'
    # ... preencher linhas do DRE
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output

async def gerar_dre_pdf(dre_data: dict, periodo: dict) -> BytesIO:
    output = BytesIO()
    doc = SimpleDocTemplate(output)
    # ... montar tabela PDF
    return output
```

**Dependências:**
```bash
pip install reportlab
# openpyxl já está no requirements.txt
```

**Testes antes do commit:**
```bash
pytest tests/test_exports.py -v
```

**Testes a criar (`tests/test_exports.py`):**
- `test_export_excel_retorna_xlsx_valido`
- `test_export_pdf_retorna_pdf_valido`
- `test_comercial_export_nao_contem_ebitda`
- `test_export_respeita_rls_por_perfil`
- `test_export_sem_autenticacao_retorna_401`

**Commit:** `feat: export DRE para PDF e Excel com ReportLab + openpyxl`

---

### Task 0.7 — Persistência do Histórico de Chat
**Arquivos:** `migrations/0014_chat_historico.sql` (novo), `app/ai/orchestrator.py`, `app/routers/chat.py`

```sql
-- migrations/0014_chat_historico.sql
CREATE TABLE chat_conversas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuarios(id),
    titulo TEXT,
    criada_em TIMESTAMPTZ DEFAULT now(),
    atualizada_em TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chat_mensagens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversa_id UUID NOT NULL REFERENCES chat_conversas(id),
    role TEXT CHECK (role IN ('user', 'assistant')),
    conteudo TEXT NOT NULL,
    tool_calls JSONB,
    criada_em TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE chat_conversas ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_mensagens ENABLE ROW LEVEL SECURITY;

CREATE POLICY usuario_proprias_conversas ON chat_conversas
    FOR ALL USING (usuario_id = auth.uid());

CREATE POLICY usuario_proprias_mensagens ON chat_mensagens
    FOR ALL USING (
        conversa_id IN (SELECT id FROM chat_conversas WHERE usuario_id = auth.uid())
    );
```

**Testes antes do commit:**
```bash
pytest tests/test_chat_historico.py -v
```

**Testes a criar:**
- `test_nova_conversa_criada_ao_iniciar_chat`
- `test_historico_persistido_apos_mensagens`
- `test_refresh_mantem_historico`
- `test_usuario_nao_ve_conversas_de_outros` (RLS)
- `test_limite_50_conversas_por_usuario`

**Commit:** `feat: persistência de histórico de chat (chat_conversas + chat_mensagens)`

---

### Task 0.8 — Tela de Gestão de Usuários (Frontend)
**Arquivos:** `frontend/app/dashboard/usuarios/page.tsx` (novo), `frontend/components/UsuariosView.tsx` (novo)

**Pré-requisito:** backend `app/routers/configuracoes.py` já tem `usuario_service.py`. Verificar se existe router `/usuarios` ou adicionar.

**Testes antes do commit:**
```bash
pytest tests/test_api.py -k "usuario" -v
cd frontend && pnpm test -- --testPathPattern="usuarios"
```

**Testes a criar:**
- `test_admin_lista_usuarios`
- `test_admin_cria_usuario`
- `test_admin_desativa_usuario_soft_delete`
- `test_gestor_nao_pode_criar_usuario` → 403
- `test_usuario_criado_recebe_email_supabase`

**Commit:** `feat(frontend): tela de gestão de usuários para Admin`

---

### Checklist de Commit — Sprint 0

```bash
# Antes do PR do Sprint 0, rodar tudo:
pytest tests/ -v
pytest tests/test_rate_limit.py
pytest tests/test_security_headers.py
pytest tests/test_exports.py
pytest tests/test_chat_historico.py
cd frontend && pnpm test
```

---

## Sprint 1 — Performance
**Branch:** `refactor/sprint-1-performance`  
**Duração estimada:** 1–2 semanas  
**Dependência:** Sprint 0 mergeado

### Task 1.1 — Índices Compostos ✅ (já implementado)
Validar que `migration/0010_indices.sql` está aplicado e índices estão em uso.

```bash
# Verificar com EXPLAIN ANALYZE
pytest tests/test_performance.py -k "index_scan" -v
```

### Task 1.2 — Migrar para asyncpg (eliminar PostgREST)
**Arquivo:** `app/database.py`, todos os services

O projeto já usa asyncpg como fallback. Task é torná-lo padrão e remover dependência do PostgREST.

```python
# app/database.py — asyncpg com set_config para RLS
async def get_connection(jwt_token: str):
    conn = await pool.acquire()
    await conn.execute(
        "SELECT set_config('request.jwt.claims', $1, true)",
        jwt_token
    )
    return conn
```

**Testes antes do commit:**
```bash
pytest tests/test_api.py -v  # todos os 87 testes devem passar
# benchmark: registrar latência antes e depois em docs/benchmark.md
```

**Commit:** `refactor: asyncpg como driver padrão, remove dependência PostgREST`

### Task 1.3 — Endpoint GET /dashboard (resposta agregada)
**Arquivo:** `app/routers/dashboard.py` (novo)

```python
# GET /dashboard — retorna DRE + metas + alertas em uma única query
@router.get('/dashboard')
async def get_dashboard(inicio: date, fim: date, usuario=Depends(ExigeTodos)):
    dre, metas, alertas = await asyncio.gather(
        buscar_dre(inicio, fim, usuario, db),
        buscar_metas(inicio, usuario, db),
        buscar_alertas(usuario, db)
    )
    return {'dre': dre, 'metas': metas, 'alertas': alertas}
```

**Testes antes do commit:**
```bash
pytest tests/test_api.py::test_dashboard_retorna_agregado -v
pytest tests/test_api.py::test_dashboard_respeita_rls -v
```

**Testes a criar:**
- `test_dashboard_retorna_dre_metas_alertas`
- `test_dashboard_comercial_sem_ebitda`
- `test_dashboard_latencia_unica_chamada` (p95 < 300ms)

**Commit:** `feat: endpoint GET /dashboard agregado (DRE + metas + alertas em uma chamada)`

### Tasks 1.4 e 1.5
- **1.4** (Promise.all frontend): depende do frontend — implementar junto com Sprint 0 Task 0.3
- **1.5** (Cache role): ✅ já implementado em `app/auth.py`

**Testes finais Sprint 1:**
```bash
pytest tests/test_api.py -v  # 87+ testes passando
# Registrar latência em docs/benchmark.md
```

---

## Sprint 2 — Segurança de Dados
**Branch:** `refactor/sprint-2-seguranca`  
**Duração estimada:** 1 semana  
**Dependência:** Sprint 1

### Task 2.1 — RLS Estornos por Produtor
**Arquivo:** `migrations/0015_fix_rls_estornos.sql` (novo)

```sql
-- migrations/0015_fix_rls_estornos.sql
DROP POLICY IF EXISTS "estornos_todos" ON estornos;

CREATE POLICY comercial_proprios_estornos ON estornos
    FOR SELECT USING (
        get_meu_role() = 'comercial' AND
        apolice_id IN (
            SELECT id FROM apolices WHERE produtor_id = get_meu_produtor()
        )
    );

CREATE POLICY gestor_equipe_estornos ON estornos
    FOR SELECT USING (
        get_meu_role() = 'gestor' AND
        apolice_id IN (
            SELECT id FROM apolices WHERE equipe_id = get_minha_equipe()
        )
    );

CREATE POLICY admin_contador_todos_estornos ON estornos
    FOR SELECT USING (get_meu_role() IN ('admin', 'contador'));
```

**Testes antes do commit (CRÍTICO):**
```bash
# Verificar ANTES (quantos estornos Comercial vê)
pytest tests/test_rls.py::test_comercial_nao_ve_estornos_de_outros -v
```

**Testes a criar:**
- `test_comercial_nao_ve_estornos_de_outros_produtores`
- `test_gestor_ve_apenas_estornos_da_equipe`
- `test_admin_ve_todos_estornos`

**Commit:** `fix(rls): estornos filtrados por produtor para perfil Comercial`

### Task 2.2 — Despesas Sensíveis Ocultas para Gestor
**Arquivo:** `migrations/0016_rls_despesas.sql` (novo)

```sql
-- Gestor não vê pessoal, pró-labore e não-operacional
DROP POLICY IF EXISTS "gestor_todas_despesas" ON despesas;

CREATE POLICY gestor_despesas_nao_sensiveis ON despesas
    FOR SELECT USING (
        get_meu_role() = 'gestor' AND
        categoria NOT IN ('pessoal', 'nao_operacional', 'investimento_imobilizado')
    );
```

**Testes antes do commit:**
```bash
pytest tests/test_rls.py::test_gestor_nao_ve_despesas_sensiveis -v
```

**Commit:** `fix(rls): despesas de pessoal e não-operacional invisíveis para Gestor`

### Task 2.3 — Soft-Delete em Despesas
**Arquivo:** `migrations/0017_soft_delete.sql` (novo), `app/services/financeiro_service.py`

```sql
-- migrations/0017_soft_delete.sql
ALTER TABLE despesas ADD COLUMN IF NOT EXISTS deletado_em TIMESTAMPTZ;
ALTER TABLE despesas ADD COLUMN IF NOT EXISTS deletado_por UUID REFERENCES usuarios(id);

-- Ocultar deletadas de todas as queries
CREATE OR REPLACE FUNCTION nao_deletadas_despesas() 
RETURNS SETOF despesas AS $$
    SELECT * FROM despesas WHERE deletado_em IS NULL;
$$ LANGUAGE sql SECURITY INVOKER;
```

```python
# app/services/financeiro_service.py — substituir DELETE físico por soft-delete
async def deletar_despesa(despesa_id: UUID, usuario: Usuario, db) -> None:
    await db.table('despesas').update({
        'deletado_em': datetime.utcnow().isoformat(),
        'deletado_por': str(usuario.id)
    }).eq('id', str(despesa_id)).execute()
```

**Testes antes do commit:**
```bash
pytest tests/test_rls.py::test_soft_delete_esconde_despesa_do_dre -v
```

**Testes a criar:**
- `test_despesa_soft_deleted_nao_aparece_no_dre`
- `test_despesa_soft_deleted_nao_listada`
- `test_despesa_deletada_permanece_no_banco` (auditoria)
- `test_apenas_admin_pode_deletar`

**Commit:** `feat: soft-delete em despesas (deletado_em, deletado_por)`

### Task 2.4 — Metas Readonly para Comercial
**Arquivo:** `migrations/0018_rls_metas.sql` (novo)

```sql
-- Remove INSERT/UPDATE/DELETE para Comercial
DROP POLICY IF EXISTS "metas_comercial_escrita" ON metas;

-- Comercial: apenas SELECT
CREATE POLICY comercial_metas_readonly ON metas
    FOR SELECT USING (
        get_meu_role() = 'comercial' AND
        (escopo = 'produtor' AND escopo_id = get_meu_produtor())
    );
```

**Testes antes do commit:**
```bash
pytest tests/test_rls.py::test_comercial_nao_cria_meta -v
```

**Testes a criar:**
- `test_comercial_recebe_403_ao_criar_meta`
- `test_comercial_recebe_403_ao_editar_meta`
- `test_gestor_pode_criar_meta_para_equipe`

**Commit:** `fix(rls): metas somente leitura para perfil Comercial`

### Task 2.5 — Status 'pendente' Default para Não-Admin
**Arquivo:** `app/services/financeiro_service.py`

```python
async def criar_despesa(payload: DespesaCreate, usuario: Usuario, db) -> DespesaItem:
    status_inicial = 'aprovada' if usuario.role in ('admin', 'contador') else 'pendente'
    dados = {**payload.model_dump(), 'status': status_inicial, 'criado_por': str(usuario.id)}
    resultado = await db.table('despesas').insert(dados).execute()
    return DespesaItem(**resultado.data[0])
```

**Testes antes do commit:**
```bash
pytest tests/test_api.py -k "despesa" -v
```

**Testes a criar:**
- `test_despesa_criada_por_comercial_entra_pendente`
- `test_despesa_criada_por_admin_entra_aprovada`
- `test_despesa_criada_por_contador_entra_aprovada`

**Commit:** `fix: despesas criadas por não-admin entram com status=pendente`

### Checklist de Commit — Sprint 2

```bash
pytest tests/test_rls.py -v          # RLS crítico
pytest tests/test_api.py -v          # 90+ testes
pytest tests/test_seguranca.py -v    # novos testes do sprint
```

---

## Sprint 3 — Regras de Negócio + ETL
**Branch:** `refactor/sprint-3-regras-negocio`  
**Duração estimada:** 1–2 semanas  
**Dependência:** Sprint 2

### Task 3.1 — Fechamento Mensal ✅ (já implementado)
Verificar que migration 0013 está aplicada e bloqueio de escrita em período fechado está funcionando.

**Teste de regressão:**
```bash
pytest tests/test_api.py -k "fechamento" -v
```

### Task 3.2 — DRE Híbrido (Snapshot para fechado, real-time para aberto)
**Arquivo:** `app/services/dre_service.py`, `migrations/0019_dre_hibrido.sql` (novo)

```python
async def buscar_dre(inicio: date, fim: date, usuario: Usuario, db) -> DREResponse:
    # Verificar se período está fechado
    fechamento = await db.table('fechamentos')\
        .select('snapshot_dre')\
        .eq('competencia', inicio.isoformat())\
        .is_('reaberto_em', 'null')\
        .maybe_single()\
        .execute()
    
    if fechamento.data:
        # Usar snapshot imutável (< 10ms)
        return DREResponse(**fechamento.data['snapshot_dre'])
    else:
        # Calcular em tempo real
        return await _calcular_dre_realtime(inicio, fim, usuario, db)
```

**Testes antes do commit:**
```bash
pytest tests/test_api.py -k "dre" -v
```

**Testes a criar:**
- `test_dre_periodo_fechado_usa_snapshot`
- `test_dre_snapshot_latencia_menor_10ms`
- `test_dre_periodo_aberto_calcula_realtime`
- `test_insert_em_periodo_fechado_falha`

**Commit:** `feat: DRE híbrido — snapshot para período fechado, real-time para aberto`

### Task 3.3 — Fix `atingimento_metas` (COUNT vs SUM)
**Arquivo:** `migrations/0020_fix_metas.sql` (novo)

```sql
-- migrations/0020_fix_metas.sql
CREATE OR REPLACE FUNCTION atingimento_metas(competencia DATE)
RETURNS JSONB AS $$
DECLARE resultado JSONB;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'meta_id', m.id,
            'metrica', m.metrica,
            'valor_alvo', m.valor_alvo,
            'valor_atual', CASE m.metrica
                WHEN 'numero_apolices' THEN  -- FIX: era SUM, deve ser COUNT
                    (SELECT COUNT(*)::numeric FROM apolices 
                     WHERE DATE_TRUNC('month', emitida_em) = DATE_TRUNC('month', competencia))
                ELSE
                    (SELECT COALESCE(SUM(valor), 0) FROM comissoes
                     WHERE DATE_TRUNC('month', competencia) = DATE_TRUNC('month', competencia))
            END
        )
    ) INTO resultado FROM metas m
    WHERE DATE_TRUNC('month', m.competencia) = DATE_TRUNC('month', competencia);
    
    RETURN resultado;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER;
```

**Testes antes do commit:**
```bash
pytest tests/test_api.py::test_metas_numero_apolices_usa_count -v
```

**Testes a criar:**
- `test_meta_numero_apolices_retorna_count_nao_sum`
- `test_meta_receita_bruta_retorna_sum`
- `test_atingimento_100pct_quando_meta_igual_real`

**Commit:** `fix(sql): atingimento_metas usa COUNT para metrica numero_apolices`

### Task 3.4 — Migrar `categoria` Legado → `tipo_lancamento_id`
**Arquivo:** `migrations/0021_migrar_categoria.sql` (novo)

```sql
-- Migrar despesas existentes que têm categoria mas não têm tipo_lancamento_id
UPDATE despesas d
SET tipo_lancamento_id = tl.id
FROM tipos_lancamento tl
WHERE d.tipo_lancamento_id IS NULL
  AND tl.categoria = d.categoria::TEXT
  AND d.categoria IS NOT NULL;
```

**Testes antes do commit:**
```bash
# Verificar que nenhuma despesa ficou sem tipo_lancamento_id
pytest tests/test_migrations.py::test_sem_despesas_sem_tipo_lancamento -v
```

**Commit:** `fix(data): migrar campo legado categoria para tipo_lancamento_id`

### Task 3.5 — ETL via API (Upload + Preview + Confirmar)
**Arquivos:** `app/services/etl_service.py` (novo), `app/routers/importacao.py` (novo)

O ETL manual em `etl/import_balancete.py` já existe. Task é expor via API.

```python
# app/routers/importacao.py
@router.post('/importacao/balancete')
async def upload_balancete(
    file: UploadFile,
    usuario: Usuario = Depends(ExigeAdminContador)
) -> PreviewImportacao:
    conteudo = await file.read()
    preview = await processar_balancete_preview(conteudo)
    return preview

@router.post('/importacao/balancete/confirmar')
async def confirmar_importacao(
    payload: ConfirmarImportacao,
    usuario: Usuario = Depends(ExigeAdminContador)
) -> ResultadoImportacao:
    resultado = await efetivar_importacao(payload.lancamentos, usuario, db)
    await registrar_auditoria(usuario, 'importacao_balancete', {'total': resultado.total}, db_admin)
    return resultado
```

**Testes antes do commit:**
```bash
pytest tests/test_importacao.py -v
```

**Testes a criar (`tests/test_importacao.py`):**
- `test_upload_excel_retorna_preview`
- `test_preview_contem_lancamentos_mapeados`
- `test_preview_contem_nao_mapeados`
- `test_confirmar_efetiva_registros_no_banco`
- `test_importacao_registrada_em_audit_log`
- `test_gestor_nao_pode_importar` → 403

**Commit:** `feat: ETL balancete via API (upload, preview, confirmar)`

---

## Sprint 4 — Multi-Tenant
**Branch:** `feature/sprint-4-multi-tenant`  
**Duração estimada:** 2–3 semanas  
**Dependência:** Sprint 3

> **Atenção:** este sprint tem impacto em TODAS as tabelas. Requer backup antes e rollback script pronto.

### Tasks 4.1–4.5 (resumo)

| Task | Arquivo | Ação |
|---|---|---|
| 4.1 | `migrations/0022_tenants.sql` | Criar tabela `tenants` + planos + seed MX Seguros |
| 4.2 | `migrations/0023_add_tenant_id.sql` | Adicionar `tenant_id` em 16+ tabelas |
| 4.3 | `migrations/0024_rls_multitenant.sql` | RLS com `get_meu_tenant()` em toda policy |
| 4.4 | `app/middleware/tenant.py` | Middleware: resolve tenant pelo subdomínio/header |
| 4.5 | `app/routers/admin_platform.py` | Role `super_admin`, rotas `/platform/*` |

**Testes críticos antes do commit (cada task):**
```bash
pytest tests/test_isolamento_tenant.py -v
```

**Testes a criar (`tests/test_isolamento_tenant.py`):**
- `test_tenant_a_nao_ve_dados_tenant_b`
- `test_request_sem_tenant_retorna_403`
- `test_super_admin_acessa_platform`
- `test_admin_normal_nao_acessa_platform`

**Commit por task:**
```bash
# 4.1
git commit -m "feat(multi-tenant): tabela tenants + planos + seed"
# 4.2
git commit -m "feat(multi-tenant): tenant_id em todas as tabelas operacionais"
# 4.3 — CRÍTICO, revisar policies antes
git commit -m "feat(multi-tenant): RLS com isolamento por tenant"
# 4.4
git commit -m "feat(multi-tenant): middleware de resolução de tenant"
# 4.5
git commit -m "feat(multi-tenant): role super_admin e rotas /platform/*"
```

---

## Sprint 5 — Onboarding e Theming
**Branch:** `feature/sprint-5-onboarding`  
**Duração estimada:** 2 semanas  
**Dependência:** Sprint 4

| Task | Descrição |
|---|---|
| 5.1 | Theming dinâmico por tenant (logo, cores) |
| 5.2 | Setup wizard (primeiro acesso do tenant) |
| 5.3 | Wildcard DNS + SSL automático |

**Testes antes de cada commit:**
```bash
cd frontend && pnpm test
pytest tests/test_api.py -v
```

---

## Sprint 6 — Billing e Limites
**Branch:** `feature/sprint-6-billing`  
**Duração estimada:** 1–2 semanas  
**Dependência:** Sprint 5

| Task | Descrição |
|---|---|
| 6.1 | Validação de limites por plano (usuários, mensagens IA) |
| 6.2 | Integração Stripe/Asaas |
| 6.3 | Dashboard do super_admin (métricas, faturamento) |

**Testes antes de cada commit:**
```bash
pytest tests/test_billing.py -v
pytest tests/test_api.py -v
```

---

## Sprint 7 — Observabilidade e DevOps
**Branch:** `infra/sprint-7-observabilidade`  
**Duração estimada:** 1 semana  
**Pode rodar em paralelo com:** Sprint 2 ou Sprint 3

### Task 7.1 — Logging Estruturado (structlog)
**Arquivos:** `app/logging_config.py` (novo), todos os routers

```python
# app/logging_config.py
import structlog

def setup_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt='iso'),
            structlog.processors.JSONRenderer(),
        ]
    )
```

**Testes antes do commit:**
```bash
pip install structlog
pytest tests/test_logging.py -v
```

**Testes a criar:**
- `test_log_dre_calculado_contem_campos_obrigatorios`
- `test_log_chat_contem_tokens_e_tools`
- `test_sem_print_no_codigo` (grep por print() em app/)

**Commit:** `feat(observabilidade): logging estruturado via structlog (JSON em prod)`

### Task 7.2 — Health Check Detalhado ✅ (parcialmente feito)
Expandir o GET /health existente:

```python
# GET /health/detailed — apenas super_admin
@router.get('/health/detailed')
async def health_detailed(usuario=Depends(ExigeSuperAdmin)):
    return {
        'db_pool_size': pool.get_size(),
        'db_pool_free': pool.get_idle_size(),
        'requests_last_hour': await contar_requests_ultima_hora(),
        'avg_response_ms': await media_response_ms()
    }
```

**Commit:** `feat(observabilidade): health check detalhado para super_admin`

### Task 7.3 — CI/CD GitHub Actions
**Arquivos:** `.github/workflows/ci.yml` (novo), `.github/workflows/deploy.yml` (novo)

```yaml
# .github/workflows/ci.yml
name: CI
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.12'}
      - run: pip install -r requirements.txt
      - run: ruff check app/
      - run: pytest tests/ -v --tb=short
```

**Testes antes do commit:**
```bash
# Simular CI localmente
ruff check app/ && pytest tests/ -v
```

**Commit:** `feat(ci): GitHub Actions — lint + testes em todo PR`

### Task 7.4 — Rotação de Audit Log
**Arquivo:** `migrations/0025_audit_retention.sql` (novo)

```sql
CREATE TABLE audit_log_archive (LIKE audit_log INCLUDING ALL);

CREATE OR REPLACE FUNCTION rotacionar_audit_log() RETURNS void AS $$
BEGIN
    INSERT INTO audit_log_archive SELECT * FROM audit_log
    WHERE criado_em < now() - interval '90 days';
    
    DELETE FROM audit_log WHERE criado_em < now() - interval '90 days';
END;
$$ LANGUAGE plpgsql;
```

**Testes antes do commit:**
```bash
pytest tests/test_audit_retention.py -v
```

**Commit:** `feat(infra): rotação automática de audit_log (90 dias → archive)`

---

## Checklist Geral antes de Go-Live

```bash
# Rodar TODOS os testes
pytest tests/ -v --tb=short

# Testes críticos de segurança
pytest tests/test_rls.py -v
pytest tests/test_adversarial.py -v
pytest tests/test_isolamento_tenant.py -v

# Frontend
cd frontend && pnpm test && pnpm build

# Lint
ruff check app/ && ruff format --check app/

# Health check
curl https://api.dreapp.com.br/health
```

---

## Resumo Executivo

| Sprint | Semanas | Tasks | Status atual |
|---|---|---|---|
| **Sprint 0** — Dívida Técnica | 1–2 | 8 | ❌ 0/8 prontas |
| **Sprint 1** — Performance | 1–2 | 5 | ✅ 2/5 prontas (1.1, 1.5) |
| **Sprint 2** — Segurança | 1 | 5 | ⚠️ 0.5/5 (parcial em 2.5) |
| **Sprint 3** — Regras + ETL | 1–2 | 5 | ✅ 1.5/5 (3.1 feito, 3.5 parcial) |
| **Sprint 4** — Multi-Tenant | 2–3 | 5 | ❌ 0/5 prontas |
| **Sprint 5** — Onboarding | 2 | 3 | ❌ 0/3 prontas |
| **Sprint 6** — Billing | 1–2 | 3 | ❌ 0/3 prontas |
| **Sprint 7** — DevOps | 1 | 4 | ✅ 1/4 (7.2 feito) |
| **TOTAL** | **10–15 sem** | **38** | **~13% completo** |

**Ordem recomendada de execução:**
1. Sprint 0 (bugs que afetam operação hoje)
2. Sprint 2 (bugs de segurança — P0)
3. Sprint 7 (pode rodar em paralelo com Sprint 2)
4. Sprint 1 (performance)
5. Sprint 3 (regras + ETL)
6. Sprint 4, 5, 6 (expansão SaaS)
