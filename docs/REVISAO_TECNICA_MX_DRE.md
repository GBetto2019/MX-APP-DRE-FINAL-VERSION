# REVISÃO TÉCNICA — MX DRE-IA
## De monolito single-tenant para SaaS multi-tenant

**Data:** 28/05/2026
**Baseado em:** DOCUMENTACAO_MX_DRE.md v1.0 (27/05/2026)
**Objetivo:** Diagnosticar lentidão, revisar arquitetura/segurança/regras, e propor caminho para transformar o app em produto SaaS.

---

## PARTE 1 — DIAGNÓSTICO DA LENTIDÃO

Analisei a documentação completa e identifiquei **7 causas prováveis** de lentidão. Organizei da mais provável para a menos.

### 1.1. PostgREST como intermediário desnecessário (CAUSA PRINCIPAL PROVÁVEL)

O backend usa `supabase-py` para chamar RPCs e fazer queries. O fluxo real é:

```
Frontend → FastAPI → supabase-py → PostgREST (HTTP) → PostgreSQL
```

Ou seja, para cada chamada de serviço, o FastAPI faz um **request HTTP para o PostgREST**, que faz uma query no Postgres, serializa para JSON, devolve para o `supabase-py`, que desserializa, e o FastAPI serializa de novo para devolver ao frontend. São **duas camadas de HTTP + duas serializações JSON** que não precisam existir.

**Proposta: conexão direta ao Postgres via `asyncpg`.**

```
Frontend → FastAPI → asyncpg → PostgreSQL (direto)
```

O `asyncpg` é um driver nativo async para Postgres escrito em Cython — é 3-10x mais rápido que PostgREST para queries complexas como o DRE. A RLS continua funcionando: basta setar o role do JWT na sessão do Postgres antes de cada query.

```python
# Como manter RLS com asyncpg (sem PostgREST)
async def execute_as_user(pool, jwt_claims, query, *args):
    async with pool.acquire() as conn:
        # Seta o role e claims do usuário na sessão do Postgres
        await conn.execute(
            "SELECT set_config('request.jwt.claims', $1, true)",
            json.dumps(jwt_claims)
        )
        await conn.execute(
            "SELECT set_config('role', 'authenticated', true)"
        )
        return await conn.fetch(query, *args)
```

**Impacto estimado:** redução de 40-60% na latência de todas as queries. É a mudança de maior impacto.

**Custo:** médio. Precisa refatorar `dre_service.py` e `financeiro_service.py` — trocar chamadas `.rpc()` e `.from_()` por queries `asyncpg` diretas. As funções SQL e RLS não mudam.

### 1.2. DRE calculado em tempo real a cada requisição

A função `dre_por_periodo()` executa **6 subqueries** (receitas, estornos, impostos, repasses, despesas fixas, despesas não-operacionais) toda vez que é chamada. Com 10k apólices/mês e um ano de dados, são JOINs pesados rodando sob demanda.

**Proposta: materialized view com refresh incremental.**

```sql
-- View materializada que pré-calcula DRE mensal
CREATE MATERIALIZED VIEW mv_dre_mensal AS
SELECT
  date_trunc('month', c.competencia) AS mes,
  a.equipe_id,
  a.produtor_id,
  SUM(c.valor) AS receita_bruta,
  -- ... demais agregações
FROM comissoes c
JOIN apolices a ON a.id = c.apolice_id
GROUP BY 1, 2, 3;

CREATE UNIQUE INDEX idx_mv_dre ON mv_dre_mensal(mes, equipe_id, produtor_id);

-- Refresh após cada INSERT/batch
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dre_mensal;
```

A `dre_por_periodo()` passa a ler da view materializada (leitura de índice, ~5ms) em vez de calcular do zero (~200-500ms).

**Refresh**: trigger ou cron (a cada 5 min, ou após batch de importação). Para dados do mês corrente, pode manter o cálculo em tempo real e usar a view para meses fechados.

**Impacto estimado:** 10-50x mais rápido para consultas de DRE histórico.

### 1.3. Frontend fazendo chamadas sequenciais

No Fluxo 1 da documentação (§10):

> "Frontend exibe tabela + chama api.dreRamos() **em paralelo**"

Mas o `DashboardOverview.tsx` provavelmente carrega DRE + comissões + estornos + metas + repasses. Se essas chamadas forem sequenciais (await um depois do outro), o tempo total é a **soma** de todas.

**Proposta:**

```typescript
// ANTES (sequencial — lento)
const dre = await api.dre(token, inicio, fim);
const estornos = await api.estornos(token, inicio, fim);
const metas = await api.metas(token, competencia);

// DEPOIS (paralelo — rápido)
const [dre, estornos, metas] = await Promise.all([
  api.dre(token, inicio, fim),
  api.estornos(token, inicio, fim),
  api.metas(token, competencia),
]);
```

E melhor ainda: criar **um endpoint agregado** no backend:

```
GET /dashboard?inicio=2026-01-01&fim=2026-03-31
```

Que retorna DRE + estornos + metas + KPIs num único request. Uma ida ao banco, uma serialização, uma resposta.

**Impacto:** se hoje são 5 chamadas sequenciais de ~300ms cada, cai de ~1.5s para ~400ms.

### 1.4. Supabase-py cria um novo httpx.Client a cada chamada

Se o `get_supabase_usuario(jwt)` instancia um novo `Client()` do Supabase a cada request, há overhead de TLS handshake + pool de conexões HTTP sendo criado e descartado. Mesmo com PostgREST, reutilizar o client faz diferença.

**Proposta (se manter supabase-py por ora):**

```python
# Cache de clients por JWT (TTL curto, ex: 5 min)
from functools import lru_cache
import time

_client_cache = {}

def get_supabase_usuario(jwt: str):
    now = time.time()
    if jwt in _client_cache and now - _client_cache[jwt][1] < 300:
        return _client_cache[jwt][0]
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=...)
    client.auth.set_session(jwt)
    _client_cache[jwt] = (client, now)
    return client
```

### 1.5. Ausência de índices nas colunas de filtro

As queries mais frequentes filtram por `competencia`, `equipe_id`, `produtor_id` e `status`. Se não há índices compostos, o Postgres faz seq scan em tabelas grandes.

**Proposta:**

```sql
-- Índices críticos para performance do DRE
CREATE INDEX idx_comissoes_competencia ON comissoes(competencia);
CREATE INDEX idx_comissoes_apolice ON comissoes(apolice_id);
CREATE INDEX idx_estornos_competencia ON estornos(competencia_estorno);
CREATE INDEX idx_repasses_competencia_status ON repasses(competencia, status);
CREATE INDEX idx_despesas_competencia_status ON despesas(competencia, status);
CREATE INDEX idx_apolices_equipe_produtor ON apolices(equipe_id, produtor_id);
CREATE INDEX idx_apolices_emitida ON apolices(emitida_em);
```

**Impacto:** pode ser dramático se as tabelas já passaram de 100k linhas. Rode `EXPLAIN ANALYZE` na `dre_por_periodo()` para confirmar.

### 1.6. Auth: busca de role no banco a cada request

Segundo §3: "Busca role SEMPRE do banco (nunca do JWT)". Seguro, mas implica um SELECT na tabela `usuarios` em **todo** request, antes da lógica de negócio.

**Proposta:** cache em memória com TTL de 60s. Role não muda com frequência.

```python
import asyncio
from cachetools import TTLCache

_role_cache = TTLCache(maxsize=200, ttl=60)

async def get_user_role(user_id: str, db) -> str:
    if user_id in _role_cache:
        return _role_cache[user_id]
    role = await db.fetchval(
        "SELECT role FROM usuarios WHERE id = $1", user_id
    )
    _role_cache[user_id] = role
    return role
```

### 1.7. SSE do chat sem backpressure

O streaming SSE do chat manda chunks conforme o Claude gera. Se a conexão do cliente é lenta (mobile 3G), o backend bufferiza tudo em memória. Com 50 usuários no chat ao mesmo tempo, isso consome RAM.

**Proposta:** não é causa de lentidão do DRE, mas é risco de estabilidade. Implementar timeout (30s sem chunk → encerra) e limite de conexões SSE simultâneas (ex: 20).

---

### Resumo de prioridade de performance

| # | Ação | Impacto | Esforço | Prioridade |
|---|---|---|---|---|
| 1 | asyncpg direto (eliminar PostgREST) | Alto | Médio | P0 |
| 2 | Materialized view para DRE | Alto | Baixo | P0 |
| 3 | Endpoint agregado /dashboard | Médio | Baixo | P1 |
| 4 | Promise.all no frontend | Médio | Baixo | P1 |
| 5 | Índices compostos | Médio-Alto | Baixo | P0 |
| 6 | Cache de role | Baixo-Médio | Baixo | P2 |
| 7 | Cache de supabase client | Baixo | Baixo | P2 |

---

## PARTE 2 — REVISÃO DE SEGURANÇA

### 2.1. Problemas encontrados

**CRÍTICO — Estornos abertos para todos:**
Na matriz de acesso (§5), estornos têm SELECT liberado para **todos os perfis**, inclusive Comercial. Mas a documentação original diz que Comercial só vê estornos das **suas** apólices. Se a RLS permite que qualquer Comercial veja todos os estornos, ele pode inferir volume de negócios de outros produtores pelo tamanho/frequência dos estornos.

**Recomendação:** alinhar RLS de estornos com a mesma lógica de comissões — Comercial vê apenas estornos vinculados a apólices onde `produtor_id = get_meu_produtor()`.

**ALTO — Despesas visíveis para Gestor (todas):**
Gestores veem **todas** as despesas, incluindo pró-labore, distribuição de lucros e salários individuais que estejam lançados como despesa. A documentação do escopo original previa que essas informações fossem restritas a Admin e Contador.

**Recomendação:** filtrar na RLS para Gestor: `despesas WHERE categoria NOT IN ('pessoal', 'nao_operacional')` OU criar tabela separada para despesas sensíveis.

**MÉDIO — Delete de despesas sem soft-delete:**
Admin pode deletar despesas via `DELETE /lancamentos/despesas/{id}`. Em sistema financeiro, deleção física é arriscada — impede auditoria retroativa ("a despesa X sumiu do DRE de março, quem apagou?").

**Recomendação:** trocar DELETE por soft-delete (`status = 'excluida'`, `excluido_por`, `excluido_em`). A `audit_log` registra, mas o registro na própria tabela é mais confiável para reconciliação.

**MÉDIO — CRUD de metas aberto para Comercial:**
A tabela `metas` permite INSERT/UPDATE/DELETE para Comercial (§5.RLS). Um Comercial poderia, em tese, criar uma meta irrealista para si mesmo ou alterar o `valor_alvo` para mostrar 100% atingido no dashboard.

**Recomendação:** Comercial deveria ter apenas SELECT em metas. Criação/edição de metas por Admin e Gestor (da sua equipe).

**BAIXO — Audit log sem proteção contra truncamento:**
O `detalhes` do audit_log é truncado em 500/2000 chars. Se uma pergunta do chat contiver payload malicioso longo, o truncamento pode cortar justamente a parte relevante para investigação.

**Recomendação:** guardar hash SHA-256 do conteúdo completo + versão truncada. Permite verificar integridade sem armazenar tudo.

### 2.2. Checklist de segurança para SaaS

Quando virar multi-tenant (Parte 4), será necessário:

- [ ] Isolamento de dados por tenant (RLS com `tenant_id` em toda tabela)
- [ ] Chaves de API separadas por tenant (nunca compartilhar `service_role`)
- [ ] Rate limiting por tenant (não só global)
- [ ] Backup/restore por tenant individual
- [ ] LGPD: direito de exclusão por tenant completo
- [ ] Penetration test antes do primeiro cliente externo

---

## PARTE 3 — REVISÃO DE REGRAS DE NEGÓCIO

### 3.1. Problemas no DRE

**Função `atingimento_metas()` não trata métrica `numero_apolices`:**
A própria documentação reconhece (nota após tabela `metas` em §4): "Se a metrica for `numero_apolices`, a função SQL precisa ser atualizada para COUNT." Isso não é um bug futuro — é um bug **agora**, se alguém criar uma meta com essa métrica.

**Proposta:**

```sql
-- Dentro de atingimento_metas():
CASE m.metrica
  WHEN 'receita_bruta' THEN COALESCE(SUM(c.valor), 0)
  WHEN 'comissao_liquida' THEN COALESCE(SUM(c.valor), 0) - COALESCE(SUM(r.valor), 0)
  WHEN 'numero_apolices' THEN COUNT(DISTINCT a.id)
END AS valor_atual
```

**Campo legado `categoria` na tabela `despesas`:**
A documentação diz que `tipo_lancamento_id` é o caminho novo, mas `dre_por_periodo()` precisa tratar ambos. Isso é dívida técnica que cresce — toda query nova precisa do `COALESCE(tipo_lancamento.custo_tipo, categoria)` dance. Quando virar SaaS, novos tenants não terão dados legados.

**Proposta:** migration de limpeza que popula `tipo_lancamento_id` para todas as despesas existentes que usam só `categoria`, depois torna `tipo_lancamento_id NOT NULL` e remove a lógica de fallback.

**Despesa default `status='aprovada'`:**
O fluxo de aprovação existe mas está desligado por default ("retrocompatibilidade"). Em sistema financeiro, o padrão deveria ser o inverso: `status='pendente'` para não-admin, com aprovação obrigatória. O estado atual permite que um Comercial insira despesas que entram direto no DRE sem revisão.

### 3.2. Gaps de regra de negócio

**Fechamento mensal não existe:**
Não há mecanismo para "fechar" um período. Qualquer pessoa com permissão de escrita pode alterar retroativamente despesas de meses passados, mudando o DRE histórico sem rastro (além do audit_log genérico). Para SaaS com múltiplos clientes, isso é inaceitável.

**Proposta:** tabela `fechamentos_mensais`:

```sql
CREATE TABLE fechamentos_mensais (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  competencia DATE NOT NULL UNIQUE,
  fechado_por UUID REFERENCES usuarios(id),
  fechado_em TIMESTAMPTZ DEFAULT now(),
  snapshot_dre JSONB NOT NULL -- foto do DRE no momento do fechamento
);
```

+ RLS que impede INSERT/UPDATE/DELETE em registros com competência fechada. Admin pode reabrir (com log).

**Conciliação bancária ausente:**
O sistema sabe quando uma comissão foi reconhecida (competência) e quando foi recebida (recebida_em), mas não cruza com extrato bancário. Para uma corretora que opera com 25+ seguradoras, cada uma com prazo de repasse diferente, a conciliação é vital.

**Proposta (Fase futura):** tabela `movimentacoes_bancarias` + tela de conciliação que cruza comissão prevista × crédito efetivo.

---

## PARTE 4 — DE SINGLE-TENANT PARA SAAS MULTI-TENANT

Esta é a mudança mais estrutural. Vou detalhar o que precisa mudar e o que pode ficar para depois.

### 4.1. Estratégia de multi-tenancy: qual modelo

Existem 3 modelos clássicos:

| Modelo | Isolamento | Custo | Complexidade |
|---|---|---|---|
| **Banco separado por tenant** | Máximo | Alto (um Postgres por cliente) | Baixa (cada um é independente) |
| **Schema separado por tenant** | Alto | Médio (um schema por cliente) | Média |
| **Mesmo banco, coluna `tenant_id`** | Baixo-Médio (RLS) | Baixo | Alta (toda query precisa do filtro) |

**Recomendação para o seu caso: coluna `tenant_id`**, pelos seguintes motivos:

- Você já tem RLS montada — adicionar `tenant_id` nas políticas é incremental, não reescrever.
- Supabase cobra por projeto (banco). 50 clientes × projeto = custo alto.
- O volume por tenant (10k apólices) cabe tranquilo num Postgres único.
- Corretoras de seguro são um nicho regulado mas não ultra-sensível (não é saúde com HIPAA).

**Modelo futuro se escalar para 500+ tenants**: schema separado (mais isolamento, backups individuais).

### 4.2. Mudanças no banco de dados

**Tabela nova: `tenants`**

```sql
CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome TEXT NOT NULL,          -- "MX Seguros", "ABC Corretora"
  cnpj TEXT UNIQUE,
  slug TEXT UNIQUE NOT NULL,   -- "mx-seguros" (usado em URLs e subdomínio)
  regime_tributario TEXT CHECK (regime_tributario IN (
    'simples_nacional', 'lucro_presumido', 'lucro_real'
  )) NOT NULL,
  aliquota_padrao NUMERIC(6,4),
  plano TEXT CHECK (plano IN ('trial', 'starter', 'pro', 'enterprise'))
    DEFAULT 'trial',
  ativo BOOLEAN DEFAULT true,
  criado_em TIMESTAMPTZ DEFAULT now(),
  configuracoes JSONB DEFAULT '{}'::jsonb
    -- ex: {"moeda": "BRL", "fuso": "America/Sao_Paulo",
    --      "ramos_customizados": ["AGRO", "TRANSPORTES"],
    --      "logo_url": "...",
    --      "cores": {"primaria": "#0C1934"}}
);
```

**Coluna `tenant_id` em TODAS as tabelas de negócio:**

```sql
-- Adicionar a cada tabela existente:
ALTER TABLE equipes ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE produtores ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE usuarios ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE seguradoras ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE ramos ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE apolices ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE comissoes ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE repasses ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE estornos ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE despesas ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE impostos ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE metas ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE bancos ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE centros_custo ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE tipos_lancamento ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE receitas_outras ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE audit_log ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE fechamentos_mensais ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
```

**Índice em toda tabela:** `CREATE INDEX idx_<tabela>_tenant ON <tabela>(tenant_id);`

**Helper function:**

```sql
CREATE OR REPLACE FUNCTION get_meu_tenant() RETURNS UUID AS $$
  SELECT tenant_id FROM usuarios WHERE id = auth.uid()
$$ LANGUAGE sql STABLE SECURITY INVOKER;
```

**RLS atualizada (padrão para toda tabela):**

```sql
-- Antes (single-tenant):
CREATE POLICY admin_all ON comissoes FOR SELECT
  USING (EXISTS (SELECT 1 FROM usuarios WHERE id = auth.uid() AND role = 'admin'));

-- Depois (multi-tenant):
CREATE POLICY admin_all ON comissoes FOR SELECT
  USING (
    tenant_id = get_meu_tenant()
    AND EXISTS (SELECT 1 FROM usuarios WHERE id = auth.uid() AND role = 'admin')
  );
```

O `tenant_id = get_meu_tenant()` é a **primeira** condição em toda policy. Assim, mesmo que alguma outra condição falhe, o isolamento entre tenants é garantido.

### 4.3. Mudanças no backend

**Middleware de tenant:**

```python
# Toda requisição resolve o tenant antes de qualquer lógica
async def resolve_tenant(request: Request) -> Tenant:
    # Opção 1: subdomínio (mx-seguros.dreapp.com.br)
    host = request.headers.get("host", "")
    slug = host.split(".")[0]
    # Opção 2: header (X-Tenant-Slug: mx-seguros)
    # Opção 3: path (/api/v1/mx-seguros/dre) — menos recomendado

    tenant = await get_tenant_by_slug(slug)
    if not tenant or not tenant.ativo:
        raise HTTPException(403, "Tenant não encontrado ou inativo")
    return tenant
```

**API versionada:**

```
# Hoje:
GET /dre?inicio=...&fim=...

# SaaS:
GET /api/v1/dre?inicio=...&fim=...
# ou
GET https://mx-seguros.dreapp.com.br/api/v1/dre?inicio=...&fim=...
```

### 4.4. Mudanças no frontend

**Theming por tenant:**
Hoje as cores estão hardcoded (§9). Para SaaS, elas vêm do `tenants.configuracoes`:

```typescript
// Carrega do banco no login, aplica como CSS variables
document.documentElement.style.setProperty('--cor-primaria', tenant.cores.primaria);
```

**Logo e branding por tenant:**
Logo vem de `tenants.configuracoes.logo_url`. Landing page vira genérica com formulário de onboarding.

**Subdomínio ou path:**
Cada corretora acessa via `slug.dreapp.com.br`. O middleware do Next.js resolve o tenant pelo hostname.

### 4.5. O que configura por tenant

| Item | Hoje (hardcoded para MX) | SaaS (configurável) |
|---|---|---|
| Ramos de seguro | ENUM fixo | Tabela por tenant + ramos padrão |
| Regime tributário | Simples 3,5% | Campo no tenant |
| Seguradoras | Lista fixa | Tabela por tenant (com catálogo global opcional) |
| Centros de custo | `matriz`, `aguas_lindoia` | CRUD por tenant |
| Cores / logo | Hardcoded | `tenants.configuracoes` |
| Tipos de lançamento | Preset MX | Preset genérico + CRUD por tenant |
| Moeda | BRL implícito | Campo no tenant (para futuro LATAM) |

### 4.6. Novo perfil: `super_admin`

Para administrar o SaaS em si (não um tenant), precisa de um role novo:

```sql
ALTER TYPE user_role ADD VALUE 'super_admin';
```

Capacidades:
- Criar/desativar tenants
- Ver métricas de uso (queries/dia, custo IA, armazenamento)
- Gerenciar planos e billing
- Acessar qualquer tenant como "impersonate" (com log)

Esse role **não** faz parte da RLS normal — é tratado separadamente, com `service_role` key.

### 4.7. Billing e limites por plano

```sql
CREATE TABLE planos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome TEXT NOT NULL,           -- 'trial', 'starter', 'pro', 'enterprise'
  max_usuarios INT,             -- 5, 20, 50, ilimitado
  max_apolices_mes INT,         -- 500, 5000, 50000, ilimitado
  max_chat_mensagens_dia INT,   -- 10, 50, 200, ilimitado
  preco_mensal_centavos INT,    -- 0, 9900, 29900, 59900
  ativo BOOLEAN DEFAULT true
);
```

O backend valida limites antes de criar registros:

```python
async def validar_limites_tenant(tenant_id, recurso):
    plano = await get_plano_do_tenant(tenant_id)
    uso = await get_uso_atual(tenant_id, recurso)
    if uso >= plano.limite[recurso]:
        raise HTTPException(
            402, f"Limite do plano atingido: {recurso}"
        )
```

---

## PARTE 5 — ROADMAP DE IMPLEMENTAÇÃO

Ordem recomendada, considerando que você quer **testar com a MX primeiro** e depois abrir para outros.

### Sprint 1 — Performance (1-2 semanas)
Resolva a lentidão antes de qualquer mudança estrutural.

- [ ] Criar índices compostos (§1.5) — 30 min
- [ ] Implementar `Promise.all` no frontend — 2h
- [ ] Criar endpoint agregado `/dashboard` — 4h
- [ ] Cache de role em memória — 2h
- [ ] Investigar: rodar `EXPLAIN ANALYZE` na `dre_por_periodo()` com dados reais → confirmar gargalo
- [ ] Se confirmado PostgREST como gargalo: migrar para `asyncpg` (maior esforço do sprint)

### Sprint 2 — Correções de segurança e regras (1 semana)

- [ ] RLS de estornos: filtrar por produtor para Comercial
- [ ] RLS de despesas: ocultar sensíveis para Gestor
- [ ] Soft-delete em despesas (trocar DELETE por `status='excluida'`)
- [ ] Restringir metas: Comercial apenas SELECT
- [ ] Corrigir `atingimento_metas()` para `numero_apolices`
- [ ] Migrar despesas legadas de `categoria` para `tipo_lancamento_id`
- [ ] Implementar `despesa.status = 'pendente'` como default para não-admin

### Sprint 3 — Fechamento mensal + materialized view (1 semana)

- [ ] Tabela `fechamentos_mensais` + RLS que bloqueia escrita em período fechado
- [ ] Materialized view `mv_dre_mensal` + refresh automático
- [ ] `dre_por_periodo()` usa view para meses fechados, cálculo real para mês corrente

### Sprint 4 — Preparação multi-tenant (2-3 semanas)

- [ ] Tabela `tenants` + `planos`
- [ ] Migration: adicionar `tenant_id` em todas as tabelas (popular com tenant MX para dados existentes)
- [ ] Atualizar TODAS as políticas RLS com `tenant_id = get_meu_tenant()`
- [ ] Middleware de tenant no backend
- [ ] Testes: criar tenant fictício "Corretora Teste" e validar isolamento total
- [ ] API versionada (`/api/v1/`)

### Sprint 5 — Onboarding + theming (2 semanas)

- [ ] Fluxo de criação de tenant (super_admin)
- [ ] Theming dinâmico por tenant (cores, logo)
- [ ] Setup wizard para novo tenant (criar equipes, produtores, ramos, bancos)
- [ ] Seed de dados padrão por tenant (ramos padrão, tipos de lançamento genéricos)
- [ ] Subdomínio via wildcard DNS (*.dreapp.com.br)

### Sprint 6 — Billing + limites (1-2 semanas)

- [ ] Integração Stripe (ou equivalente BR como Asaas/Pagar.me)
- [ ] Validação de limites por plano em cada endpoint
- [ ] Dashboard de super_admin com métricas por tenant
- [ ] Página de pricing pública

---

## PARTE 6 — RESUMO EXECUTIVO DAS MUDANÇAS

### O que muda AGORA (Sprints 1-3, antes de virar SaaS):

| Área | Mudança | Risco de não fazer |
|---|---|---|
| Performance | asyncpg + índices + materialized view + /dashboard | App continua lento, usuários desistem |
| Segurança | RLS de estornos e despesas + soft-delete + metas | Vazamento de dados entre produtores |
| Regras | Fechamento mensal + fix atingimento_metas + status pendente | DRE retroativamente alterável, metas erradas |

### O que muda DEPOIS (Sprints 4-6, para virar SaaS):

| Área | Mudança | Pode esperar? |
|---|---|---|
| Banco | `tenant_id` em tudo + RLS reescrita | Sim, mas faça antes do 2º cliente |
| Backend | Middleware tenant + API v1 + billing | Sim |
| Frontend | Theming dinâmico + onboarding wizard | Sim |
| Infra | Wildcard DNS + Stripe | Sim |
| Novo role | `super_admin` | Sim |

### O que NÃO muda:

- Stack fundamental (Postgres + FastAPI + Next.js + Claude) — está bem escolhida.
- Modelo de autenticação (Supabase Auth + JWT) — correto.
- Princípio de "LLM não calcula" — manter.
- Estrutura de tabelas (schema) — só adiciona `tenant_id`, não reestrutura.
- Sistema de tools do Claude — só precisa receber `tenant_id` no contexto.

---

## APÊNDICE A — Checklist rápido antes de começar qualquer Sprint

```
□ Rodei EXPLAIN ANALYZE na dre_por_periodo() com dados reais?
□ Tenho backup do banco antes da migration?
□ Os testes existentes (test_rls.py, test_api.py) ainda passam?
□ Testei com os 4 perfis (admin, gestor, comercial, contador)?
□ Audit log registra a mudança?
```

---

**Próximo passo recomendado:** comece pelo Sprint 1 (performance). É o problema que o usuário sente hoje. Os Sprints 2-3 são dívida técnica que precisa ser paga antes de abrir para outros clientes. Os Sprints 4-6 são a transformação em SaaS.

Se quiser, posso detalhar qualquer sprint em tasks granulares com prompts para o Claude Code no Cursor, no mesmo formato que fizemos no escopo original.
