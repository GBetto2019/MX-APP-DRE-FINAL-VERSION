# SDD — MX DRE-IA · Software Design Document
**Versão:** 4.0  
**Data:** 09/06/2026  
**Autor:** Gabriel Betto  
**Status:** Produção

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura do Sistema](#2-arquitetura-do-sistema)
3. [Frontend (Next.js)](#3-frontend-nextjs)
4. [Backend (FastAPI)](#4-backend-fastapi)
5. [Banco de Dados (Supabase/PostgreSQL)](#5-banco-de-dados-supabasepostgresql)
6. [Autenticação e Autorização](#6-autenticação-e-autorização)
7. [Inteligência Artificial (Claude API)](#7-inteligência-artificial-claude-api)
8. [Infraestrutura e Deploy](#8-infraestrutura-e-deploy)
9. [Segurança](#9-segurança)
10. [APIs — Referência Completa](#10-apis--referência-completa)
11. [Modelos de Dados](#11-modelos-de-dados)
12. [Fluxos Principais](#12-fluxos-principais)
13. [Variáveis de Ambiente](#13-variáveis-de-ambiente)
14. [Sprints e Estado de Implementação](#14-sprints-e-estado-de-implementação)
15. [Problemas Conhecidos e Decisões Técnicas](#15-problemas-conhecidos-e-decisões-técnicas)

---

## 1. Visão Geral

### 1.1 Propósito

O **MX DRE-IA** substitui planilhas Excel usadas pela MX Corretora de Seguros para gestão financeira. O sistema oferece:

- DRE (Demonstração do Resultado do Exercício) calculado em tempo real via SQL
- Controle de lançamentos financeiros (receitas e despesas) por banco e centro de custo
- Assistente conversacional com IA (Claude) para análise financeira
- Exportação em PDF e Excel
- Controle de acesso por perfil (Admin, Gestor, Comercial, Contador)
- Multi-tenancy para futura expansão (múltiplas corretoras)

### 1.2 Tecnologias Principais

| Camada | Tecnologia | Versão | Hospedagem |
|--------|-----------|--------|-----------|
| Frontend | Next.js + TypeScript + Tailwind CSS | 14.2.15 | Vercel |
| Backend | FastAPI + Python | 3.11+ | Railway |
| Banco | PostgreSQL + Supabase Auth | PostgreSQL 15 | Supabase |
| IA | Claude API (Anthropic) | claude-sonnet-4-5 | API externa |
| ORM/Query | asyncpg (direto) + supabase-py (fallback) | — | — |

### 1.3 URLs de Produção

| Serviço | URL |
|---------|-----|
| Frontend | https://mx-app-dre-final-version.vercel.app |
| Backend API | https://alert-patience-production-86b7.up.railway.app |
| API Docs (Swagger) | https://alert-patience-production-86b7.up.railway.app/docs |
| Supabase Dashboard | https://supabase.com/dashboard/project/jrqmntvmtukmhlmnukgn |

---

## 2. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                     USUÁRIO (Browser)                    │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTPS
┌───────────────────────▼─────────────────────────────────┐
│              VERCEL (CDN + Edge Network)                 │
│  Next.js 14 — App Router — SSG + Client Components      │
│  Autenticação: @supabase/ssr + createBrowserClient       │
└──────────┬────────────────────────────┬─────────────────┘
           │ JWT (Bearer)               │ Supabase Auth API
           │ REST                       │ (signInWithPassword)
┌──────────▼──────────┐    ┌───────────▼───────────────────┐
│   RAILWAY (FastAPI) │    │      SUPABASE                 │
│                     │    │  ┌─────────────────────────┐  │
│  14 Routers         │    │  │ Auth (JWT ES256)         │  │
│  asyncpg pool       │◄───┼──│ PostgreSQL 15           │  │
│  supabase-py        │    │  │ PostgREST (REST API)     │  │
│  Claude API client  │    │  │ RLS (Row Level Security) │  │
│  Rate limiting      │    │  │ SQL Functions            │  │
│  CORS restritivo    │    │  └─────────────────────────┘  │
└──────────┬──────────┘    └───────────────────────────────┘
           │ HTTPS
┌──────────▼──────────┐
│  ANTHROPIC API      │
│  claude-sonnet-4-5  │
│  (Chat + Insights)  │
└─────────────────────┘
```

### 2.1 Padrão de Comunicação

1. **Browser → Supabase Auth:** Login direto via `@supabase/ssr`. O JWT é armazenado no cookie do browser.
2. **Browser → Railway:** Todas as chamadas de negócio carregam o JWT no header `Authorization: Bearer <token>`.
3. **Railway → Supabase PostgreSQL:** asyncpg via `DATABASE_URL` (direto ao Postgres) quando disponível; fallback para PostgREST via `supabase-py`.
4. **Railway → Claude API:** Chamadas SSE (Server-Sent Events) para streaming de respostas.

---

## 3. Frontend (Next.js)

### 3.1 Estrutura de Diretórios

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout (HTML, meta, fontes)
│   │   ├── page.tsx                # Redirect para /dashboard
│   │   ├── login/
│   │   │   └── page.tsx            # Tela de login
│   │   └── dashboard/
│   │       ├── layout.tsx          # Layout do dashboard (sidebar, auth guard)
│   │       ├── page.tsx            # Visão Geral (KPIs + Insights IA)
│   │       ├── dre/page.tsx        # DRE + gráfico por ramo
│   │       ├── assistente/page.tsx # Chat com IA (SSE streaming)
│   │       ├── chat/page.tsx       # Redirect para /assistente
│   │       ├── lancamentos/
│   │       │   ├── page.tsx        # Lista de lançamentos
│   │       │   └── aprovacoes/page.tsx
│   │       ├── exports/page.tsx    # Exportação PDF/Excel
│   │       ├── usuarios/page.tsx   # Gestão de usuários (admin)
│   │       ├── configuracoes/page.tsx
│   │       └── ajuda/page.tsx
│   ├── hooks/
│   │   └── useAuth.ts              # Hook de autenticação (Supabase)
│   ├── lib/
│   │   ├── supabase.ts             # createBrowserClient (com stripBom)
│   │   ├── api.ts                  # Cliente HTTP para Railway (com stripBom)
│   │   └── utils.ts                # fmtBRL, mesAnterior, etc.
│   ├── components/
│   │   └── ui/
│   │       ├── Skeleton.tsx
│   │       ├── Badge.tsx
│   │       └── ErrorBoundary.tsx
│   └── types/
│       └── index.ts                # Interfaces TypeScript
├── public/
│   ├── logo_beige.png
│   ├── logo_dark.png
│   └── icon.png
├── .env.local                      # Variáveis locais (não versionado)
├── next.config.js
├── tailwind.config.ts
└── package.json
```

### 3.2 Roteamento e Auth Guard

O `dashboard/layout.tsx` protege todas as rotas filhas:

```tsx
// Se não há sessão → spinner → Supabase redireciona para /login
// Se há sessão → renderiza o layout com sidebar
```

A sessão é verificada via `useAuth()` hook que usa `supabase.auth.getSession()` + `onAuthStateChange`.

### 3.3 Componentes Principais

| Componente | Localização | Responsabilidade |
|-----------|-------------|-----------------|
| `useAuth` | `hooks/useAuth.ts` | Sessão, token JWT, signIn/signOut |
| `createClient` | `lib/supabase.ts` | Instância do Supabase browser client |
| `api` | `lib/api.ts` | GET/POST/PUT/PATCH/DELETE para Railway |
| `streamChat` | `lib/api.ts` | SSE streaming para chat com IA |
| `Skeleton` | `components/ui/Skeleton.tsx` | Loading states |

### 3.4 Observações de Build

- **BOM (Byte Order Mark):** O `.env` local usa codificação UTF-8-BOM. Ambos `supabase.ts` e `api.ts` implementam `stripBom()` defensivo: `s.charCodeAt(0) === 0xFEFF ? s.slice(1) : s`.
- **Cache Vercel:** `VERCEL_FORCE_NO_BUILD_CACHE=1` foi ativado para evitar que o webpack reutilize módulos compilados com variáveis de ambiente antigas.
- **Monorepo Vercel:** O `vercel.json` usa `@vercel/next` apontando para `frontend/package.json` e inclui rewrite para `/_next/(.*)` (necessário quando o projeto não está na raiz).

---

## 4. Backend (FastAPI)

### 4.1 Estrutura

```
app/
├── main.py              # Ponto de entrada, CORS, middlewares, routers
├── config.py            # Configurações via pydantic-settings
├── auth.py              # JWT validation, obter_usuario_atual, UsuarioAtual
├── database.py          # asyncpg pool, get_supabase_*, conn_as_user
├── logging_config.py    # structlog JSON structured logging
├── middleware/
│   ├── rate_limit.py    # slowapi (limite por IP)
│   ├── tenant.py        # Injeta tenant_id no contexto
│   └── periodo.py       # Valida datas de período
├── models/
│   └── schemas.py       # Pydantic models (request/response)
├── routers/
│   ├── health.py        # GET /health
│   ├── platform.py      # GET /platform/info
│   ├── dashboard.py     # GET /dashboard, GET /dashboard/insights (SSE)
│   ├── dre.py           # GET /dre, /dre/ramos, /dre/impostos
│   ├── chat.py          # GET /chat/stream (SSE), GET /chat/historico
│   ├── lancamentos.py   # CRUD /lancamentos
│   ├── exports.py       # GET /exports/pdf, /exports/excel
│   ├── comissoes.py     # GET /comissoes
│   ├── estornos.py      # GET /estornos
│   ├── metas.py         # CRUD /metas
│   ├── repasses.py      # GET /repasses
│   ├── fechamentos.py   # CRUD /fechamentos
│   ├── importacao.py    # POST /importacao/excel
│   ├── configuracoes.py # GET/PUT /configuracoes
│   └── usuarios.py      # CRUD /usuarios, GET /usuarios/me
├── services/
│   ├── dre_service.py      # Lógica DRE (buscar_dre, receita_por_ramo)
│   ├── dashboard_service.py
│   ├── chat_service.py     # Orquestra Claude API + histórico
│   ├── export_service.py   # ReportLab (PDF) + openpyxl (Excel)
│   ├── etl_service.py      # Importação Excel
│   ├── fechamento_service.py
│   ├── financeiro_service.py
│   └── usuario_service.py
└── ai/
    └── tools.py         # Claude tool definitions para análise financeira
```

### 4.2 CORS

```python
# Origens permitidas (produção)
allow_origins = [
    "https://mx-app-dre-final-version.vercel.app",  # Vercel
    "http://localhost:3000",                          # Dev local
    "http://localhost:3001",
]
```

### 4.3 Middlewares (ordem de execução)

1. **SlowAPI** — Rate limiting por IP (configurable)
2. **CORSMiddleware** — Controle de origens
3. **TenantMiddleware** — Injeta `tenant_id` no request state
4. **Security Headers** — `X-Content-Type-Options`, `X-Frame-Options`, `HSTS` (produção)

### 4.4 Padrão de Query (asyncpg vs PostgREST)

```python
def _pool():
    return get_asyncpg_pool()  # None se DATABASE_URL não configurado

# Em cada service:
if _pool():
    async with conn_as_user(usuario_id) as conn:
        result = await conn.fetchrow("SELECT ...")  # asyncpg direto
else:
    resp = db.rpc("funcao_sql", {...}).execute()    # PostgREST fallback
```

**Exceção:** `buscar_receita_por_ramo` usa sempre PostgREST (problema de `SET LOCAL ROLE` no asyncpg com Supabase).

---

## 5. Banco de Dados (Supabase/PostgreSQL)

### 5.1 Migrations Aplicadas

| Migration | Descrição |
|-----------|-----------|
| 0001_schema.sql | Schema base: usuários, ramos, apolices, comissoes, despesas |
| 0002_rls.sql | Row Level Security em todas as tabelas |
| 0003_functions.sql | Funções SQL: `dre_por_periodo`, `receita_por_ramo`, `taxa_estorno` |
| 0004_seed.sql | Dados iniciais: ramos, tipos de lançamento |
| 0005–0011 | Índices, performance, ajustes de schema |
| 0012_sprint2.sql | RLS despesas, soft-delete, metas readonly Comercial |
| 0013_fechamentos.sql | Tabela `fechamentos_mensais` |
| 0014_chat.sql | Tabelas `chat_conversas`, `chat_mensagens` |
| 0015_audit.sql | Audit log com retenção 90 dias |
| 0016_tipo_lancamento.sql | Migração categoria → `tipo_lancamento_id` |
| 0017–0019_multitenant.sql | Tabela `tenants`, coluna `tenant_id` em todas as tabelas, RLS multi-tenant |

### 5.2 Tabelas Principais

```sql
usuarios          -- Perfis de acesso (id = auth.uid() do Supabase Auth)
tenants           -- Corretoras (multi-tenancy)
ramos             -- Ramos de seguro (AUTO, VIDA, SAUDE, etc.)
apolices          -- Apólices por ramo e produtor
comissoes         -- Receitas de comissão por apólice
despesas          -- Lançamentos de despesa
tipos_lancamento  -- Categorias de lançamento
metas             -- Metas mensais por equipe
repasses          -- Repasses para produtores
fechamentos_mensais -- Snapshots mensais do DRE
chat_conversas    -- Sessões de chat com IA
chat_mensagens    -- Mensagens individuais (role: user/assistant)
audit_log         -- Log imutável de todas as ações
```

### 5.3 Funções SQL Principais

| Função | Retorno | Uso |
|--------|---------|-----|
| `dre_por_periodo(inicio, fim)` | JSONB | Calcula DRE completo |
| `receita_por_ramo(inicio, fim)` | JSONB | Agrega receita por ramo |
| `taxa_estorno(inicio, fim)` | NUMERIC | Taxa de estorno (%) |
| `get_meu_tenant()` | UUID | Retorna tenant_id do usuário logado |
| `is_super_admin()` | BOOLEAN | Verifica se é super_admin |
| `_tenant_ok(tenant_id)` | BOOLEAN | Macro para RLS multi-tenant |

### 5.4 RLS (Row Level Security)

Todas as tabelas têm RLS ativo. A política base é:

```sql
-- Usuário só vê dados do seu tenant
CREATE POLICY tabela_select ON tabela
    FOR SELECT TO authenticated
    USING (_tenant_ok(tenant_id));
```

`_tenant_ok(p_tenant_id)` = `p_tenant_id = get_meu_tenant() OR is_super_admin()`

---

## 6. Autenticação e Autorização

### 6.1 Fluxo de Login

```
1. Browser: supabase.auth.signInWithPassword({ email, password })
2. Supabase Auth: valida credenciais → retorna JWT (ES256, 1h de validade)
3. Browser: armazena JWT em cookie (gerenciado por @supabase/ssr)
4. Browser: toda requisição para Railway inclui Authorization: Bearer <JWT>
5. Railway: obter_usuario_atual() valida JWT via supabase.auth.get_user(token)
6. Railway: busca role, tenant_id, equipe_id, produtor_id na tabela usuarios
7. Cache em memória: {user_id: (role, tenant_id, ..., timestamp)} TTL = 5 min
```

### 6.2 Perfis de Acesso

| Role | Descrição | Restrições |
|------|-----------|-----------|
| `admin` | Acesso total | — |
| `gestor` | Visão gerencial | Sem gestão de usuários |
| `comercial` | Operacional | Apenas lançamentos e metas próprias |
| `contador` | Financeiro | DRE e exportações; sem modificações |
| `super_admin` | Multi-tenant | Acessa todos os tenants |

### 6.3 Modelo UsuarioAtual

```python
class UsuarioAtual(BaseModel):
    user_id:     str        # UUID do Supabase Auth
    role:        str        # admin | gestor | comercial | contador | super_admin
    tenant_id:   str | None
    equipe_id:   str | None
    produtor_id: str | None
```

---

## 7. Inteligência Artificial (Claude API)

### 7.1 Modelos Utilizados

| Funcionalidade | Modelo | Modo |
|---------------|--------|------|
| Chat assistente | claude-sonnet-4-5 | Streaming SSE |
| Insights de mercado | claude-sonnet-4-5 | Streaming SSE |

### 7.2 Chat Assistente

- **Endpoint:** `GET /chat/stream?mensagem=...&conversa_id=...&token=...`
- **Tools disponíveis** (function calling): `buscar_dre`, `buscar_comissoes`, `buscar_metas`, `buscar_receita_por_ramo`
- **Histórico:** Persistido em `chat_conversas` + `chat_mensagens` (Supabase)
- **Contexto:** Últimas 20 mensagens da conversa são enviadas para o Claude

### 7.3 Insights de Mercado

- **Endpoint:** `GET /dashboard/insights`
- **Prompt:** Análise do mercado de seguros brasileiro (fontes públicas SUSEP, CNseg)
- **Cache no frontend:** 24 horas (localStorage)

---

## 8. Infraestrutura e Deploy

### 8.1 Vercel (Frontend)

```json
// vercel.json
{
  "version": 2,
  "builds": [{ "src": "frontend/package.json", "use": "@vercel/next" }],
  "rewrites": [
    { "source": "/_next/(.*)", "destination": "/frontend/_next/$1" },
    { "source": "/((?!_next/).*)", "destination": "/frontend/$1" }
  ]
}
```

**Variáveis de Ambiente (Vercel):**
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_URL` → URL do Railway

**Como fazer deploy:**
```bash
npx vercel --prod
```

### 8.2 Railway (Backend)

```json
// railway.json
{
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 30
  }
}
```

**Variáveis de Ambiente (Railway):**
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL` → postgresql://... (Supabase connection pooler)
- `ANTHROPIC_API_KEY`
- `FRONTEND_URL` → URL do Vercel
- `ENVIRONMENT=production`

**Como fazer deploy:**
```bash
npx railway up --service alert-patience
```

### 8.3 Supabase

- Projeto ID: `jrqmntvmtukmhlmnukgn`
- Região: South America (São Paulo)
- Plano: Free tier
- Migrations aplicadas via `executar_migrations.py`

### 8.4 CI/CD

`.github/workflows/ci.yml`:
- **Backend:** `ruff` (lint) + `pytest` (testes adversariais)
- **Frontend:** `tsc --noEmit` (typecheck) + `next build`

---

## 9. Segurança

### 9.1 Medidas Implementadas

| Área | Medida |
|------|--------|
| Autenticação | JWT ES256 via Supabase Auth, 1h TTL |
| Autorização | RLS no PostgreSQL + verificação de role no backend |
| CORS | Whitelist restrita (Vercel + localhost) |
| Rate Limiting | slowapi por IP |
| Headers HTTP | `X-Content-Type-Options`, `X-Frame-Options`, `HSTS` (produção) |
| SQL Injection | Queries parametrizadas (asyncpg + PostgREST) |
| Secrets | `.env` nunca versionado; variáveis no Vercel/Railway |
| Audit Log | Toda ação registrada em `audit_log` (append-only, 90 dias) |

### 9.2 Chaves API — Formato Supabase Novo

| Tipo | Formato | Uso |
|------|---------|-----|
| Anon Key | `sb_publishable_*` | Frontend (browser) |
| Service Role | `sb_secret_*` | Backend apenas (nunca expor ao browser) |

> ⚠️ A `sb_secret_*` é bloqueada pelo Supabase quando enviada via browser (detecção de User-Agent). Usar sempre via `curl` ou server-side.

---

## 10. APIs — Referência Completa

### 10.1 Health

```
GET /health
Response: { status, version, ambiente, db, uptime_seconds }
```

### 10.2 Dashboard

```
GET /dashboard?inicio=YYYY-MM-DD&fim=YYYY-MM-DD
Authorization: Bearer <JWT>
Response: { periodo, dre: { receita_bruta, ... }, perfil, metas, alertas, latencia_ms }

GET /dashboard/insights
Authorization: Bearer <JWT>
Response: SSE stream — data: { conteudo: "..." } | data: { fim: true }
```

### 10.3 DRE

```
GET /dre?inicio=YYYY-MM-DD&fim=YYYY-MM-DD
GET /dre/ramos?inicio=YYYY-MM-DD&fim=YYYY-MM-DD
GET /dre/impostos?inicio=YYYY-MM-DD&fim=YYYY-MM-DD
```

### 10.4 Chat

```
GET /chat/stream?mensagem=...&conversa_id=...&token=<JWT>
Response: SSE stream — data: { texto: "..." } | data: { conversa_id: "..." } | data: [DONE]

GET /chat/historico?limit=20&offset=0
```

### 10.5 Lançamentos

```
GET    /lancamentos?inicio=...&fim=...&status=...
POST   /lancamentos         { valor, data, tipo_lancamento_id, banco_id, descricao }
PUT    /lancamentos/{id}
PATCH  /lancamentos/{id}/aprovar
PATCH  /lancamentos/{id}/rejeitar
DELETE /lancamentos/{id}
```

### 10.6 Usuários

```
GET  /usuarios            (admin only)
GET  /usuarios/me
POST /usuarios            { email, nome, role, senha }
PUT  /usuarios/{id}
DELETE /usuarios/{id}     (soft-delete: ativo=false)
```

### 10.7 Exportações

```
GET /exports/pdf?inicio=...&fim=...
GET /exports/excel?inicio=...&fim=...
Response: arquivo binário (application/pdf | application/vnd.openxmlformats...)
```

---

## 11. Modelos de Dados

### 11.1 DREResponse

```typescript
interface DREResponse {
  periodo: { inicio: string; fim: string }
  dre: {
    receita_bruta: number
    estornos: number
    impostos: number
    receita_liquida: number
    repasses_produtores: number
    margem_contribuicao: number
    despesas_fixas: number
    ebitda: number
    despesas_nao_operacionais: number
    resultado_liquido: number
  }
  perfil: string
}
```

### 11.2 ReceitaRamoResponse

```typescript
interface ReceitaRamoResponse {
  periodo: { inicio: string; fim: string }
  items: Array<{
    ramo_codigo: string
    ramo_nome: string
    receita_total: number
    num_apolices: number
  }>
  total: number
}
```

### 11.3 UsuarioAtual (Backend)

```python
class UsuarioAtual(BaseModel):
    user_id: str
    role: str        # admin | gestor | comercial | contador | super_admin
    tenant_id: str | None
    equipe_id: str | None
    produtor_id: str | None
```

---

## 12. Fluxos Principais

### 12.1 Login

```
Browser → supabase.auth.signInWithPassword()
       → Supabase Auth valida → JWT retornado
       → Cookie gravado pelo @supabase/ssr
       → router.push('/dashboard')
       → dashboard/layout.tsx verifica sessão
       → Renderiza dashboard
```

### 12.2 Consulta DRE

```
Frontend: api.get('/dre?inicio=...&fim=...', token)
Backend:  obter_usuario_atual() valida JWT
          dre_service.buscar_dre(inicio, fim, usuario, db)
          → asyncpg: SELECT dre_por_periodo($1, $2)
          → Retorna JSONB com todos os indicadores
Frontend: Renderiza tabela + gráfico
```

### 12.3 Chat com IA

```
Frontend: EventSource('/chat/stream?mensagem=...&token=...')
Backend:  Busca últimas 20 mensagens da conversa
          Monta context para Claude com tools disponíveis
          → Claude decide usar tool (ex: buscar_dre)
          → Backend executa tool, retorna resultado
          → Claude gera resposta final
          SSE: data: { texto: "..." } (chunks)
          SSE: data: { conversa_id: "uuid" }
          SSE: data: [DONE]
Frontend: Renderiza resposta em streaming
```

---

## 13. Variáveis de Ambiente

### 13.1 Frontend (.env.local)

```env
NEXT_PUBLIC_SUPABASE_URL=https://jrqmntvmtukmhlmnukgn.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_...
NEXT_PUBLIC_API_URL=https://alert-patience-production-86b7.up.railway.app
```

> ⚠️ Se o arquivo `.env` estiver codificado em UTF-8-BOM, as variáveis terão `﻿` no início. O código tem proteção via `stripBom()`.

### 13.2 Backend (.env / Railway)

```env
SUPABASE_URL=https://jrqmntvmtukmhlmnukgn.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
ANTHROPIC_API_KEY=sk-ant-...
FRONTEND_URL=https://mx-app-dre-final-version.vercel.app
ENVIRONMENT=production
SECRET_KEY=...
```

---

## 14. Sprints e Estado de Implementação

### 14.1 Concluído (~80% do SDD v3)

- ✅ Sprint 1: Schema, RLS, funções SQL, seed data
- ✅ Sprint 2: Segurança (RLS avançado, soft-delete, audit log)
- ✅ Sprint 3: DRE, dashboard, exportações PDF/Excel
- ✅ Sprint 4: Chat IA com streaming, histórico, tools
- ✅ Sprint 7: Multi-tenancy (tabelas, RLS, `_tenant_ok`)
- ✅ Frontend completo (Next.js 14, todas as telas)
- ✅ Deploy produção (Vercel + Railway)
- ✅ CI/CD (GitHub Actions)

### 14.2 Pendente

| Item | Sprint | Prioridade |
|------|--------|-----------|
| asyncpg direto nos services (substituir PostgREST) | 1 (Task 1.2) | Baixa |
| DRE híbrido snapshot/real-time | 3 (Task 3.2) | Média |
| Theming dinâmico por tenant | 5 | Baixa |
| Setup wizard para novo tenant | 5 | Baixa |
| Billing (Stripe/Asaas) | 6 | Futura |
| Dashboard super_admin | 6 | Futura |
| Testes frontend (Vitest) | — | Média |

---

## 15. Problemas Conhecidos e Decisões Técnicas

### 15.1 BOM em Variáveis de Ambiente

**Problema:** O arquivo `.env` local está codificado em UTF-8-BOM. Quando as variáveis `NEXT_PUBLIC_*` foram adicionadas ao Vercel copiando do `.env`, o caractere `﻿` (BOM) foi incluído, invalidando URLs e chaves.

**Solução:** Re-adição via `printf 'valor' | vercel env add VAR` (sem BOM). Proteção defensiva com `stripBom()` em `supabase.ts` e `api.ts`.

### 15.2 asyncpg + SET LOCAL ROLE

**Problema:** `conn_as_user()` executa `SET LOCAL ROLE authenticated` para ativar RLS. O usuário `postgres` do pool não tem permissão para impersonar o role `authenticated` no Supabase Cloud, causando erro na função `receita_por_ramo`.

**Solução:** `buscar_receita_por_ramo` usa sempre PostgREST (`supabase-py`) que lida com RLS automaticamente via JWT.

### 15.3 Rewrite /_next/ no Vercel

**Problema:** Monorepo com `@vercel/next` publica assets em `/frontend/_next/...` mas o HTML gerado referencia `/_next/...`, causando 404 nos chunks JS/CSS.

**Solução:** Rewrite explícito no `vercel.json`:
```json
{ "source": "/_next/(.*)", "destination": "/frontend/_next/$1" }
```

### 15.4 Supabase `sb_publishable_*` / `sb_secret_*`

**Contexto:** Novo formato de chaves Supabase (junho 2026). A `sb_secret_*` é detectada e bloqueada quando enviada via browser ou PowerShell (`Invoke-WebRequest`). Usar sempre `curl` para testes com service role.

### 15.5 Usuários de Teste

| Email | Senha | Role |
|-------|-------|------|
| admin@mxseguros.test | Teste@123 | admin |
| gestor@mxseguros.test | Teste@123 | gestor |
| comercial@mxseguros.test | Teste@123 | comercial |
| contador@mxseguros.test | Teste@123 | contador |

> ⚠️ Dados de teste concentrados em **Janeiro/2026**. Para ver o gráfico DRE com valores, selecionar o período `2026-01-01` a `2026-01-31`.

---

*Documento gerado em 09/06/2026 · MX Corretora de Seguros · Confidencial*
