# MX Seguros — DRE-IA: Documentação Completa do Projeto

> **Versão:** 1.0 — Gerado em 2026-05-27
> **Repositório:** https://github.com/GBetto2019/MX-APP-DRE
> **Uso:** Base de referência para novas funcionalidades, ajustes e onboarding

---

## Sumário

1. [Visão Geral](#1-visão-geral)
2. [Stack Tecnológica](#2-stack-tecnológica)
3. [Arquitetura do Sistema](#3-arquitetura-do-sistema)
4. [Banco de Dados](#4-banco-de-dados)
5. [Segurança e Permissões](#5-segurança-e-permissões)
6. [Backend — Endpoints da API](#6-backend--endpoints-da-api)
7. [Serviços e Lógica de Negócio](#7-serviços-e-lógica-de-negócio)
8. [Inteligência Artificial](#8-inteligência-artificial)
9. [Frontend — Estrutura e Páginas](#9-frontend--estrutura-e-páginas)
10. [Fluxos Completos](#10-fluxos-completos)
11. [Regras de Negócio](#11-regras-de-negócio)
12. [Variáveis de Ambiente](#12-variáveis-de-ambiente)
13. [Como Rodar Localmente](#13-como-rodar-localmente)
14. [Roadmap de Fases](#14-roadmap-de-fases)

---

## 1. Visão Geral

O **MX DRE-IA** é um sistema de gestão financeira voltado para a corretora **MX Seguros**, com as seguintes capacidades:

- **DRE (Demonstração do Resultado do Exercício)** por período, com campos visíveis conforme o perfil do usuário
- **Gestão de comissões, estornos, repasses e metas** com filtros automáticos por equipe e produtor
- **Lançamentos manuais** de despesas e receitas, com fluxo de aprovação
- **Configurações** de bancos, centros de custo e tipos de lançamento
- **Chat com IA** (Claude Sonnet) com acesso controlado a dados financeiros via tools

O sistema é **multi-tenant por perfil**: o mesmo banco de dados serve admin, gestores, comerciais e contadores, cada um enxergando apenas o que lhe é permitido — sem nenhuma lógica de filtro no frontend, tudo via RLS do PostgreSQL/Supabase.

---

## 2. Stack Tecnológica

### Backend
| Tecnologia | Versão | Uso |
|---|---|---|
| Python | 3.12 | Linguagem principal |
| FastAPI | 0.115+ | Framework web (REST + SSE) |
| Uvicorn | — | ASGI server |
| Supabase-py | 2.10+ | Cliente Supabase (PostgREST + Auth) |
| Pydantic v2 | — | Validação e serialização |
| Anthropic SDK | 0.40+ | Integração Claude IA |
| python-jose | — | Validação JWT |
| pandas / openpyxl | — | ETL e exportação Excel |
| pytest / pytest-asyncio | — | Testes |

### Frontend
| Tecnologia | Versão | Uso |
|---|---|---|
| Next.js | 16.2.6 | Framework React (App Router) |
| React | 19.2.4 | UI |
| TypeScript | 5 | Tipagem estática |
| Tailwind CSS | 4 | Estilização |
| Recharts | 3.8.1 | Gráficos |
| Supabase SSR | 0.10.3 | Auth + SSR |
| lucide-react | 1.16.0 | Ícones |

### Infraestrutura
| Componente | Tecnologia |
|---|---|
| Banco de dados | Supabase (PostgreSQL 15+) |
| Autenticação | Supabase Auth (JWT ES256) |
| API de IA | Anthropic Claude (`claude-sonnet-4-5`) |
| Ambiente dev | localhost:8000 (backend), localhost:3000 (frontend) |

---

## 3. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────┐
│                  FRONTEND (Next.js)             │
│  /dashboard/dre  /chat  /lancamentos  ...       │
│  lib/api.ts → apiFetch() com Bearer token       │
└─────────────────┬───────────────────────────────┘
                  │ HTTPS + Bearer JWT
┌─────────────────▼───────────────────────────────┐
│                BACKEND (FastAPI)                │
│                                                 │
│  Camada 1: app/auth.py                          │
│    └─ Valida JWT via Supabase Admin             │
│    └─ Busca role SEMPRE do banco (nunca do JWT) │
│                                                 │
│  Camada 2: app/routers/*.py                     │
│    └─ Verifica role via _exigir_roles()         │
│    └─ Passa JWT para get_supabase_usuario()     │
│                                                 │
│  Camada 3: app/services/*.py                    │
│    └─ Chama RPCs SQL com cliente JWT            │
└─────────────────┬───────────────────────────────┘
                  │ PostgREST + JWT
┌─────────────────▼───────────────────────────────┐
│             SUPABASE (PostgreSQL)               │
│                                                 │
│  RLS Policies → filtro automático por perfil   │
│  SQL Functions → dre_por_periodo(), ...         │
│  auth.users → base de usuários Supabase        │
└─────────────────────────────────────────────────┘
```

### Dois clientes Supabase com propósitos diferentes

| Cliente | Como criar | Bypass RLS? | Uso |
|---|---|---|---|
| `get_supabase_usuario(jwt)` | Com JWT do usuário | Não | Toda query de negócio |
| `get_supabase_admin()` | Service Role Key | Sim | Apenas audit log e operações admin de sistema |

### Estrutura de diretórios do Backend

```
DRE_APP/
├── app/
│   ├── main.py              # FastAPI app, CORS, routers
│   ├── auth.py              # JWT validation, role lookup, dependencies
│   ├── models/
│   │   └── schemas.py       # Todos os Pydantic models
│   ├── routers/
│   │   ├── chat.py          # POST /chat (SSE)
│   │   ├── dre.py           # GET /dre, /dre/ramos
│   │   ├── comissoes.py     # GET /comissoes
│   │   ├── estornos.py      # GET /estornos
│   │   ├── metas.py         # GET /metas
│   │   ├── repasses.py      # GET /repasses
│   │   ├── lancamentos.py   # CRUD despesas + receitas
│   │   └── configuracoes.py # CRUD bancos/centros/tipos + usuários
│   ├── services/
│   │   ├── dre_service.py   # DRE, comissões, estornos, metas, repasses
│   │   └── financeiro_service.py # Lançamentos e configurações
│   └── ai/
│       ├── orchestrator.py  # Loop tool-use Claude
│       └── tools.py         # Definição e execução das tools
├── migrations/
│   ├── 0001_init.sql        # Tabelas
│   ├── 0002_rls.sql         # Políticas RLS
│   ├── 0003_functions.sql   # Funções SQL (DRE, metas, etc.)
│   ├── 0004_seed.sql        # Dados de teste
│   ├── 0005_financeiro.sql  # Bancos, centros, tipos, receitas_outras
│   ├── 0006_regras_negocio.sql # Aprovação de despesas
│   └── TODAS_AS_MIGRATIONS.sql # Concatenação de todas
├── tests/
│   ├── test_api.py
│   ├── test_adversarial.py
│   └── setup_usuarios_teste.py
├── requirements.txt
└── .env
```

### Estrutura de diretórios do Frontend

```
frontend/
├── app/
│   ├── page.tsx                  # Landing page
│   ├── layout.tsx                # Layout raiz
│   ├── login/page.tsx            # Tela de login
│   ├── auth/callback/page.tsx    # Callback OAuth
│   └── dashboard/
│       ├── layout.tsx            # Valida auth, carrega role
│       ├── page.tsx              # Dashboard overview
│       ├── dre/page.tsx
│       ├── lancamentos/page.tsx
│       ├── estornos/page.tsx
│       ├── metas/page.tsx
│       ├── repasses/page.tsx
│       └── chat/page.tsx
├── components/
│   ├── Sidebar.tsx
│   ├── DREView.tsx
│   ├── LancamentosView.tsx
│   ├── ChatView.tsx
│   ├── EstornosView.tsx
│   ├── MetasView.tsx
│   ├── RepassesView.tsx
│   ├── ConfiguracoesView.tsx
│   ├── DashboardOverview.tsx
│   ├── KpiCard.tsx
│   └── PeriodoPicker.tsx
├── lib/
│   ├── api.ts            # Cliente HTTP + todos os tipos TypeScript
│   ├── utils.ts          # formatBRL, datas, cn()
│   └── supabase/
│       ├── client.ts
│       ├── server.ts
│       └── middleware.ts
└── public/logos/
```

---

## 4. Banco de Dados

### Diagrama de Relacionamentos

```
equipes ──── produtores ──── usuarios
   │               │
   └── apolices ───┘
         │
    ┌────┼────┬──────┐
    │    │    │      │
comissoes estornos  ...
    │
  repasses
```

### Tabelas de Cadastro

#### `equipes`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| nome | text | Nome da equipe |
| unidade | enum | `matriz`, `aguas_lindoia`, `agro` |
| gestor_id | UUID FK → usuarios | Gestor responsável |
| ativo | bool | |
| criado_em | timestamptz | |

#### `produtores`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| nome | text | |
| documento | text | CPF/CNPJ |
| tipo | enum | `interno`, `externo`, `sub_corretor` |
| equipe_id | UUID FK → equipes | |
| ativo | bool | |

#### `usuarios`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK FK → auth.users | |
| nome | text | |
| email | text | |
| role | enum | `admin`, `gestor`, `comercial`, `contador` |
| equipe_id | UUID FK → equipes | (nullable) |
| produtor_id | UUID FK → produtores | (nullable) |
| ativo | bool | |

#### `seguradoras`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| nome | text UNIQUE | |
| cnpj | text | |
| ativo | bool | |

#### `ramos`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| codigo | text UNIQUE | `AUTO`, `VIDA`, `SAUDE`, `RE`, `BENEFICIOS`, `RURAL`, `AGRO` |
| nome | text | |

### Tabelas Operacionais

#### `apolices`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| numero | text | |
| seguradora_id | UUID FK → seguradoras | |
| ramo_id | UUID FK → ramos | |
| cliente_id | UUID FK → clientes | |
| produtor_id | UUID FK → produtores | |
| equipe_id | UUID FK → equipes | |
| premio_total | numeric(15,2) | |
| inicio_vigencia / fim_vigencia | date | |
| status | enum | `ativa`, `cancelada`, `renovada` |
| emitida_em | date | |
| UNIQUE | (numero, seguradora_id) | |

#### `comissoes`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| apolice_id | UUID FK → apolices | |
| tipo | enum | `comissao_padrao`, `agenciamento`, `override_rappel` |
| valor | numeric(15,2) | |
| percentual | numeric(5,2) | |
| competencia | date | Mês de competência (dia sempre = 1) |
| recebida_em | date | |

#### `repasses`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| comissao_id | UUID FK → comissoes | |
| produtor_id | UUID FK → produtores | |
| valor | numeric(15,2) | |
| percentual | numeric(5,2) | |
| competencia | date | |
| pago_em | date | |
| status | enum | `previsto`, `pago`, `estornado` |

#### `estornos`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| apolice_id | UUID FK → apolices | |
| comissao_original_id | UUID FK → comissoes | |
| valor | numeric(15,2) | |
| motivo | text | |
| competencia_original | date | |
| competencia_estorno | date | |

### Tabelas Financeiras

#### `despesas`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| tipo_lancamento_id | UUID FK → tipos_lancamento | Preferível ao campo categoria |
| banco_id | UUID FK → bancos | |
| categoria | despesa_categoria ENUM | Legado — usar tipo_lancamento_id |
| subcategoria | text | |
| descricao | text | |
| valor | numeric(15,2) | |
| competencia | date | |
| paga_em | date | |
| centro_custo | text | `matriz`, `aguas_lindoia` |
| recorrente | bool | |
| parcela_atual / parcela_total | int | |
| **status** | enum | `pendente`, `aprovada`, `rejeitada` (default: `aprovada`) |
| **criado_por** | UUID FK → usuarios | |
| **aprovado_por** | UUID FK → usuarios | |
| **aprovado_em** | timestamptz | |
| **rejeitado_motivo** | text | |

> Campos em negrito foram adicionados na migration 0006.

#### `impostos`
| Campo | Tipo | Descrição |
|---|---|---|
| tipo | enum | `simples_nacional`, `iss`, `pis`, `cofins`, `irpj`, `csll` |
| competencia | date | |
| base_calculo | numeric | |
| aliquota | numeric | |
| valor | numeric | |

#### `metas`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| escopo | enum | `global`, `equipe`, `produtor`, `ramo` |
| escopo_id | UUID | ID do escopo (null = global) |
| competencia | date | |
| valor_alvo | numeric(15,2) | |
| metrica | enum | `receita_bruta`, `comissao_liquida`, `numero_apolices` |

> **Atenção:** A função `atingimento_metas()` sempre soma `comissoes.valor`. Se a metrica for `numero_apolices`, a função SQL precisa ser atualizada para COUNT.

### Tabelas de Configuração (Migration 0005)

#### `bancos`
| Campo | Tipo |
|---|---|
| id | UUID PK |
| nome | text UNIQUE |
| ativo | bool |

Pré-inseridos: Itaú, Santander, Sicredi.

#### `centros_custo`
| Campo | Tipo |
|---|---|
| id | UUID PK |
| nome | text |
| codigo | text UNIQUE |
| ativo | bool |

Pré-inseridos: Matriz, Águas de Lindóia.

#### `tipos_lancamento`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| nome | text | |
| natureza | enum | `despesa`, `receita` |
| categoria | text | (ex: `pessoal`, `comercial`) |
| custo_tipo | text | `fixo`, `variavel`, `nao_operacional` |
| ativo | bool | |

#### `receitas_outras`
| Campo | Tipo | Descrição |
|---|---|---|
| id | UUID PK | |
| tipo_lancamento_id | UUID FK | |
| banco_id | UUID FK | |
| centro_custo | text | |
| descricao | text | |
| valor | numeric(15,2) | |
| competencia | date | |
| recebido_em | date | |
| observacao | text | |

### Tabela de Auditoria

#### `audit_log`
| Campo | Tipo | Descrição |
|---|---|---|
| id | bigserial PK | |
| usuario_id | UUID | |
| acao | text | `consulta_dre`, `chat_ia`, `login`, `export`, etc. |
| detalhes | JSONB | Dados da ação (truncado 500/2000 chars) |
| ip | text | IP do cliente |
| criado_em | timestamptz | |

### Funções SQL (RPC)

Todas as funções são `SECURITY INVOKER` — RLS aplica automaticamente.

#### `dre_por_periodo(p_inicio DATE, p_fim DATE) → JSONB`

Calcula o DRE completo para o período, respeitando RLS:

```
receita_bruta     = SUM(comissoes.valor) + SUM(receitas_outras.valor)
estornos          = SUM(estornos.valor)
impostos          = SUM(impostos.valor)
receita_liquida   = receita_bruta - estornos - impostos
repasses_produtores = SUM(repasses.valor WHERE status != 'estornado')
margem_contribuicao = receita_liquida - repasses_produtores
despesas_fixas    = SUM(despesas WHERE categoria IN ('pessoal', 'comercial', ...))
ebitda            = margem_contribuicao - despesas_fixas
desp_nao_op       = SUM(despesas WHERE categoria = 'nao_operacional')
resultado_liquido = ebitda - desp_nao_op
```

#### Outras funções
| Função | Parâmetros | Retorna |
|---|---|---|
| `receita_por_ramo(inicio, fim)` | date, date | JSONB array por ramo |
| `taxa_estorno(inicio, fim)` | date, date | JSONB `{taxa, alerta_5pct}` |
| `comissoes_por_produtor(inicio, fim, produtor_id?)` | date, date, UUID? | JSONB array |
| `atingimento_metas(competencia)` | date | JSONB array com valor_atual/percentual |

---

## 5. Segurança e Permissões

### Os 4 Perfis

| Perfil | Quem é |
|---|---|
| `admin` | Administrador da corretora, acesso total |
| `gestor` | Líder de equipe, vê sua equipe |
| `comercial` | Produtor/corretor, vê apenas os próprios dados |
| `contador` | Contador externo, leitura total, sem config |

### Matriz de Acesso por Módulo

| Módulo | admin | gestor | comercial | contador |
|---|---|---|---|---|
| **DRE completo** | Sim | Sem despesas/EBITDA | Sem receita líquida em diante | Sim |
| **Comissões** | Todas | Da equipe | Próprias | Todas |
| **Estornos** | Todos | Todos | Todos | Todos |
| **Metas** | Todas | Global + equipe + produtores | Apenas a própria | Todas (leitura) |
| **Repasses** | Todos | Da equipe | Próprios | Todos |
| **Lançamentos (escrita)** | Sim | Não | Não | Sim |
| **Lançamentos (leitura)** | Sim | Sim (todas despesas) | Próprias despesas | Sim |
| **Aprovação despesas** | Sim | Sim | Não | Não |
| **Configurações** | Sim (tudo) | Não | Não | Não |
| **Chat IA** | Todas tools | Tools de equipe | Tools próprias | Todas tools |

### Helper Functions SQL

```sql
get_meu_role()      -- role do usuário logado (usado nas políticas RLS)
get_minha_equipe()  -- equipe_id do usuário logado
get_meu_produtor()  -- produtor_id do usuário logado
```

### Políticas RLS — Resumo

| Tabela | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| `usuarios` | Próprio \| Admin \| Contador | Admin \| Gestor | Admin \| Gestor | — |
| `apolices` | Admin/Contador \| Gestor (equipe) \| Comercial (próprio) | Admin/Gestor/Comercial | Admin/Gestor | — |
| `comissoes` | Admin/Contador \| Gestor (equipe) \| Comercial (próprio) | — | — | — |
| `despesas` | Admin/Contador \| Gestor (todas) \| Comercial (criou) | Admin/Contador/Gestor/Comercial | Admin/Gestor | Admin |
| `metas` | Admin/Contador \| Gestor (escopo) \| Comercial (própria) | Admin/Gestor/Comercial | Admin/Gestor/Comercial | Admin/Gestor/Comercial |

### Dependências FastAPI

```python
ExigeAdmin         # Apenas admin (403 para outros)
ExigeAdminContador # Admin ou Contador
ExigeTodos         # Qualquer usuário autenticado
```

---

## 6. Backend — Endpoints da API

### Base URL
- Desenvolvimento: `http://localhost:8000`
- Produção: `https://api.mxseguros.com.br` (configurar)
- Swagger: `http://localhost:8000/docs`

### Headers obrigatórios
```
Authorization: Bearer <supabase_jwt_token>
Content-Type: application/json
```

---

### POST /chat — Chat com IA (SSE)

**Roles:** Todos autenticados

**Request:**
```json
{ "mensagem": "qual foi o EBITDA do primeiro trimestre?" }
```

**Response:** Stream SSE
```
data: {"tipo": "texto", "conteudo": "O EBITDA do..."}
data: {"tipo": "tool", "nome": "consultar_dre", "status": "chamando"}
data: {"tipo": "tool", "nome": "consultar_dre", "status": "concluido"}
data: {"tipo": "texto", "conteudo": "...foi de R$ 45.000"}
data: {"tipo": "fim"}
```

---

### GET /dre — DRE do período

**Roles:** Todos (campos filtrados por role)

**Query params:**
| Param | Tipo | Exemplo |
|---|---|---|
| inicio | date | 2025-01-01 |
| fim | date | 2025-03-31 |

**Response:**
```json
{
  "periodo": { "inicio": "2025-01-01", "fim": "2025-03-31" },
  "dre": {
    "receita_bruta": 120000.00,
    "estornos": 3000.00,
    "impostos": 5000.00,
    "receita_liquida": 112000.00,  // null para comercial
    "repasses_produtores": 20000.00,
    "margem_contribuicao": 92000.00, // null para comercial
    "despesas_fixas": 40000.00,  // null para gestor/comercial
    "ebitda": 52000.00,          // null para gestor/comercial
    "despesas_nao_operacionais": 5000.00, // null para gestor/comercial
    "resultado_liquido": 47000.00  // null para gestor/comercial
  },
  "perfil": "admin"
}
```

---

### GET /dre/ramos — Receita por ramo

**Roles:** Admin, Gestor, Contador

**Query params:** `inicio`, `fim` (date)

**Response:**
```json
{
  "periodo": {...},
  "items": [
    { "ramo_codigo": "AUTO", "ramo_nome": "Automóvel", "receita_total": 50000.00, "num_apolices": 120 }
  ],
  "total": 120000.00
}
```

---

### GET /comissoes — Comissões do período

**Roles:** Todos (RLS filtra por equipe/produtor)

**Query params:** `inicio`, `fim` (date)

**Response:**
```json
{
  "total": 45,
  "items": [{ "id": "...", "apolice_id": "...", "tipo": "comissao_padrao", "valor": 1500.00, ... }],
  "soma_total": 67500.00
}
```

---

### GET /estornos — Estornos do período

**Roles:** Todos

**Query params:** `inicio`, `fim` (date)

**Response:**
```json
{
  "total": 3,
  "items": [...],
  "soma_total": 4500.00,
  "taxa_estorno": 3.75,
  "alerta_5pct": false
}
```

---

### GET /metas — Metas e atingimento

**Roles:** Todos (RLS filtra por escopo)

**Query params:** `competencia` (date, ex: `2025-01-01`)

**Response:**
```json
{
  "competencia": "2025-01-01",
  "items": [
    {
      "meta_id": "...",
      "escopo": "global",
      "escopo_id": null,
      "metrica": "receita_bruta",
      "valor_alvo": 100000.00,
      "valor_atual": 112000.00,
      "percentual": 112.0,
      "atingida": true
    }
  ]
}
```

---

### GET /repasses — Repasses a produtores

**Roles:** Todos (RLS filtra)

**Query params:** `inicio`, `fim` (date), `produtor_id` (UUID, opcional — admin/gestor)

**Response:**
```json
{
  "total": 12,
  "items": [{ "id": "...", "produtor_nome": "João Silva", "valor": 2000.00, "status": "pago", ... }],
  "soma_previsto": 25000.00,
  "soma_pago": 23000.00
}
```

---

### Lançamentos — Despesas

#### GET /lancamentos/despesas
**Roles:** Admin, Contador (leitura), Gestor, Comercial (próprias)

**Query params:** `inicio`, `fim` (date), `centro_custo` (text, opcional), `banco_id` (UUID, opcional)

**Response:**
```json
{
  "total": 15,
  "items": [{ "id": "...", "tipo_nome": "Salários", "valor": 15000.00, "status": "aprovada", ... }],
  "soma_total": 45000.00,
  "total_pendentes": 2
}
```

#### POST /lancamentos/despesas
**Roles:** Admin, Contador

**Body:**
```json
{
  "tipo_lancamento_id": "uuid",
  "banco_id": "uuid",
  "subcategoria": "Folha de Pagamento",
  "descricao": "Salários março/2025",
  "valor": 15000.00,
  "competencia": "2025-03-01",
  "paga_em": "2025-03-05",
  "centro_custo": "matriz",
  "recorrente": true
}
```

#### DELETE /lancamentos/despesas/{despesa_id}
**Roles:** Admin

---

### Lançamentos — Receitas

#### GET /lancamentos/receitas
**Roles:** Admin, Contador

**Response:**
```json
{
  "total": 48,
  "items": [{ "id": "...", "origem": "comissao", "valor": 1500.00, ... }, { "id": "...", "origem": "manual", ... }],
  "soma_comissoes": 67500.00,
  "soma_manuais": 5000.00,
  "soma_total": 72500.00
}
```

#### POST /lancamentos/receitas
**Roles:** Admin, Contador

#### DELETE /lancamentos/receitas/{receita_id}
**Roles:** Admin (apenas receitas manuais)

---

### Configurações

#### Bancos
| Método | Endpoint | Role | Body |
|---|---|---|---|
| GET | /configuracoes/bancos | Todos | — |
| POST | /configuracoes/bancos | Admin | `{nome}` |
| PUT | /configuracoes/bancos/{id} | Admin | `{nome?, ativo?}` |

#### Centros de Custo
| Método | Endpoint | Role | Body |
|---|---|---|---|
| GET | /configuracoes/centros-custo | Todos | — |
| POST | /configuracoes/centros-custo | Admin | `{nome, codigo}` |
| PUT | /configuracoes/centros-custo/{id} | Admin | `{nome?, ativo?}` |

#### Tipos de Lançamento
| Método | Endpoint | Role | Body |
|---|---|---|---|
| GET | /configuracoes/tipos?natureza=despesa | Todos | — |
| POST | /configuracoes/tipos | Admin | `{nome, natureza, categoria?, custo_tipo?}` |
| PUT | /configuracoes/tipos/{id} | Admin | `{nome?, ativo?}` |
| DELETE | /configuracoes/tipos/{id} | Admin | — |

---

## 7. Serviços e Lógica de Negócio

### dre_service.py — Funções principais

| Função | O que faz |
|---|---|
| `buscar_dre(inicio, fim, usuario, db)` | Chama RPC `dre_por_periodo`, retorna `DREResponse` |
| `buscar_comissoes(inicio, fim, usuario, db)` | Lista comissões com soma total |
| `buscar_estornos(inicio, fim, usuario, db)` | Lista estornos, calcula taxa, seta `alerta_5pct` se > 5% |
| `buscar_metas(competencia, usuario, db)` | Chama RPC `atingimento_metas`, retorna lista com percentual |
| `buscar_repasses(inicio, fim, usuario, db, produtor_id?)` | Lista repasses com soma previsto/pago |
| `buscar_receita_por_ramo(inicio, fim, db)` | Chama RPC `receita_por_ramo` |
| `registrar_auditoria(usuario, acao, detalhes, ip, db_admin)` | Insere em `audit_log` via cliente admin (bypass RLS) |

### financeiro_service.py — Funções principais

| Função | O que faz |
|---|---|
| `buscar_despesas(inicio, fim, db, centro_custo?, banco_id?)` | Lista com soma e contagem de pendentes |
| `criar_despesa(payload, usuario, db)` | INSERT em `despesas` |
| `deletar_despesa(id, db)` | DELETE em `despesas` |
| `buscar_receitas(inicio, fim, db, ...)` | Une comissões + receitas_outras, retorna somas separadas |
| `criar_receita_outra(payload, db)` | INSERT em `receitas_outras` |
| `deletar_receita_outra(id, db)` | DELETE em `receitas_outras` (apenas manuais) |
| `listar_bancos/centros/tipos` | SELECT com filtros |
| `criar_*/atualizar_*/desativar_*` | CRUD de configurações |

### Princípio fundamental

> **O LLM (Claude) nunca calcula valores financeiros.**
>
> Todos os números vêm de funções SQL determinísticas executadas com RLS ativo.
> O Claude apenas interpreta e apresenta os dados retornados pelas tools.

---

## 8. Inteligência Artificial

### Modelo utilizado
- `claude-sonnet-4-5` (Anthropic)
- Máximo de tokens: 4096
- Limite de iterações tool-use: **20** (proteção anti-loop)

### Loop de execução (orchestrator.py)

```
1. Recebe mensagem do usuário
2. Monta system prompt com:
   - Role do usuário
   - Equipe/produtor (se aplicável)
   - Data atual
   - Instruções: "nunca calcule, sempre use tools"
3. Chama Claude com lista de tools disponíveis para o perfil
4. Se stop_reason == "tool_use":
   a. Valida se o perfil pode usar a tool
   b. Executa a tool (busca dados reais do banco)
   c. Appenda resultado ao histórico
   d. Volta para o Claude
5. Quando stop_reason == "end_turn": envia SSE "fim"
6. Registra auditoria com conversa truncada
```

### Tools disponíveis por perfil

| Tool | Admin | Gestor | Comercial | Contador |
|---|---|---|---|---|
| `consultar_dre` | Sim | Sim | Sim | Sim |
| `comparar_periodos` | Sim | Sim | Sim | Sim |
| `analisar_receita_por_ramo` | Sim | Sim | Não | Sim |
| `analisar_estornos` | Sim | Sim | Sim | Sim |
| `consultar_comissoes_produtor` | Sim | Sim (equipe) | Sim (próprias) | Sim |
| `consultar_metas` | Sim | Sim | Sim | Sim |

### Segurança do Chat IA

- O LLM nunca recebe SQL, credenciais ou dados além do retorno da tool
- Cada tool valida permissão antes de executar
- Auditoria completa de cada conversa
- Limite duro de 20 iterações por mensagem previne ataques de prompt injection em loop

---

## 9. Frontend — Estrutura e Páginas

### Identidade Visual MX Seguros

| Elemento | Valor |
|---|---|
| Cor primária | `#0C1934` (azul escuro) |
| Cor secundária | `#CAE3F2` (azul claro) |
| Cor terciária | `#B5A882` (dourado) |
| Background dashboard | `#F6F6F4` |
| Paleta gráficos | `["#0C1934","#CAE3F2","#B5A882","#1E3A5F","#4A7FA5","#8B7355","#6B9BC0"]` |

### Padrão de chamada à API (lib/api.ts)

```typescript
// Todas as chamadas seguem o padrão:
const resultado = await api.MODULO.metodo(token, ...params)

// Exemplos:
const dre = await api.dre(token, "2025-01-01", "2025-03-31")
const bancos = await api.configuracoes.bancos(token)
const despesas = await api.lancamentos.despesas(token, inicio, fim)
```

### Componentes e suas responsabilidades

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| `Sidebar` | Sidebar.tsx | Navegação lateral, logout, colapso |
| `DREView` | DREView.tsx | Tabela DRE + gráfico pizza por ramo |
| `LancamentosView` | LancamentosView.tsx | CRUD despesas e receitas |
| `ChatView` | ChatView.tsx | Chat com streaming SSE |
| `EstornosView` | EstornosView.tsx | Tabela + KPI taxa estorno |
| `MetasView` | MetasView.tsx | Metas com progress bar |
| `RepassesView` | RepassesView.tsx | Repasses com filtro por produtor |
| `ConfiguracoesView` | ConfiguracoesView.tsx | CRUD bancos/centros/tipos |
| `DashboardOverview` | DashboardOverview.tsx | KPIs e resumos |
| `KpiCard` | KpiCard.tsx | Card reutilizável de métrica |
| `PeriodoPicker` | PeriodoPicker.tsx | Seletor de período (De/Até) |

### Autenticação no Frontend

O arquivo `lib/supabase/middleware.ts` intercepta todas as requisições:
- Lê o JWT do cookie
- Valida com Supabase
- Redireciona para `/login` se não autenticado ou token expirado
- Protege todo o path `/dashboard/*`

O `dashboard/layout.tsx` busca o `role` do usuário da tabela `usuarios` e injeta no contexto das páginas filhas.

---

## 10. Fluxos Completos

### Fluxo 1 — Usuário visualiza DRE

```
1. DREView.tsx carrega
2. Usuário seleciona período e confirma
3. api.dre(token, inicio, fim) → GET /dre?inicio=...&fim=...
4. auth.py valida JWT → busca role do banco
5. dre_service.buscar_dre() chamado
6. RPC dre_por_periodo() executa com cliente JWT
7. SQL aplica RLS → filtra comissões/despesas visíveis
8. Retorna DREResponse (campos null se sem permissão)
9. Frontend exibe tabela + chama api.dreRamos() em paralelo
10. Gráfico pizza renderiza com receita por ramo
```

### Fluxo 2 — Chat com IA

```
1. Usuário digita: "qual foi o EBITDA em março?"
2. POST /chat com {mensagem: "..."}
3. auth.py valida JWT → extrai usuario
4. orchestrator.processar_pergunta() inicia
5. Monta system prompt com contexto do usuário
6. Chama Claude com tools disponíveis para o role
7. Claude retorna: stop_reason="tool_use", tool="consultar_dre"
8. Backend valida permissão → executa buscar_dre()
9. Retorna dados filtrados por RLS
10. Claude processa dados e gera resposta
11. Cada chunk → SSE: {"tipo":"texto","conteudo":"..."}
12. Frontend renderiza em real-time
13. Auditoria registrada em audit_log
```

### Fluxo 3 — Criar despesa (Admin)

```
1. LancamentosView.tsx → aba Despesas → botão "Nova Despesa"
2. Modal abre com campos
3. Usuário preenche: tipo, valor, data, centro_custo
4. api.lancamentos.criarDespesa(token, payload)
5. POST /lancamentos/despesas
6. auth.py → ExigeAdminContador
7. financeiro_service.criar_despesa() → INSERT em despesas
8. registrar_auditoria()
9. Modal fecha, lista recarrega
```

### Fluxo 4 — Aprovação de despesa (Gestor)

```
1. Gestor acessa /lancamentos
2. RLS permite ver todas as despesas (gestor)
3. Vê despesa com status "pendente"
4. Clica "Aprovar"
5. PUT /lancamentos/despesas/{id} com {status: "aprovada"}
6. auth.py → valida role gestor ou admin
7. UPDATE despesas SET status='aprovada', aprovado_por=..., aprovado_em=now()
8. Auditoria registrada
9. Frontend atualiza status na tabela
```

### Fluxo 5 — Autenticação

```
1. Usuário acessa /login
2. Preenche email e senha
3. Supabase Auth retorna JWT
4. JWT salvo em cookie HttpOnly (via @supabase/ssr)
5. Middleware verifica cookie em toda requisição /dashboard/*
6. dashboard/layout.tsx busca role na tabela usuarios
7. Role injetado no contexto das páginas
8. Sidebar mostra menus conforme role
```

---

## 11. Regras de Negócio

### DRE — Visibilidade por Perfil

| Linha DRE | Admin | Gestor | Comercial | Contador |
|---|---|---|---|---|
| Receita Bruta | Sim | Sim | Sim | Sim |
| Estornos | Sim | Sim | Sim | Sim |
| Impostos | Sim | Sim | Sim | Sim |
| Receita Líquida | Sim | Sim | **Não** | Sim |
| Repasses Produtores | Sim | Sim | **Não** | Sim |
| Margem de Contribuição | Sim | Sim | **Não** | Sim |
| Despesas Fixas | Sim | **Não** | **Não** | Sim |
| EBITDA | Sim | **Não** | **Não** | Sim |
| Desp. Não Operacionais | Sim | **Não** | **Não** | Sim |
| Resultado Líquido | Sim | **Não** | **Não** | Sim |

### Metas — Escopo e visibilidade

- **Global:** Todos os perfis podem ver, apenas admin/gestor podem criar
- **Equipe:** Gestor vê as de sua equipe; outros não
- **Produtor:** Comercial vê apenas a sua própria; gestor vê as da equipe; admin vê todas
- **Ramo:** Admin e gestor

### Aprovação de Despesas

- Despesas criadas via API chegam com `status = 'aprovada'` por padrão (retrocompatibilidade)
- Quando o fluxo de aprovação estiver ativo, novas despesas por Comerciais chegam como `pendente`
- Gestor e Admin podem aprovar ou rejeitar
- Rejeição requer `motivo` obrigatório
- Apenas Admin pode deletar uma despesa

### Alerta de Estornos

- Se `taxa_estorno > 5%` → campo `alerta_5pct = true`
- Frontend deve exibir alerta visual em vermelho
- Taxa calculada como: `SUM(estornos) / SUM(receita_bruta) * 100`

### Campos Monetários

> **Regra absoluta:** Todos os valores monetários usam `Decimal` no Python e `numeric` no SQL. Nunca `float`.

### Competência

- Datas de competência são sempre o **primeiro dia do mês**: `2025-03-01`
- O frontend envia `"YYYY-MM"` e a API converte para `"YYYY-MM-01"`

### Categoria vs. tipo_lancamento_id

- `despesas.categoria` é um campo ENUM legado
- Novas despesas devem usar `tipo_lancamento_id` (FK para `tipos_lancamento`)
- A função `dre_por_periodo()` trata ambos os caminhos
- **Código novo deve usar sempre `tipo_lancamento_id`**

---

## 12. Variáveis de Ambiente

### Backend (.env)

```bash
# Ambiente
ENVIRONMENT=development         # ou "production"

# Supabase
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=eyJ...        # chave pública
SUPABASE_SERVICE_ROLE_KEY=eyJ... # chave privada (nunca exposta ao frontend)
SUPABASE_JWT_SECRET=...          # Settings > API > JWT Settings

# Banco direto (opcional, só para rodar migrations via psycopg2)
DATABASE_URL=postgresql://postgres:<senha>@<host>:5432/postgres

# IA
ANTHROPIC_API_KEY=sk-ant-...
```

### Frontend (.env.local)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000     # em produção: https://api.mxseguros.com.br
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

### Testes (.env.test)

```bash
# Sobrescreve .env para ambiente de testes
# Usuários de teste usam domínio @mxseguros.test
# Criar via: python tests/setup_usuarios_teste.py
```

---

## 13. Como Rodar Localmente

### Backend

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar .env com credenciais Supabase e Anthropic

# 3. Rodar migrations (se banco novo)
python executar_migrations.py

# 4. Iniciar servidor
uvicorn app.main:app --reload --port 8000

# Swagger disponível em: http://localhost:8000/docs
```

### Frontend

```bash
# 1. Instalar dependências
npm install

# 2. Configurar .env.local

# 3. Iniciar em modo desenvolvimento
npm run dev

# Disponível em: http://localhost:3000
```

### Testes

```bash
# Criar usuários de teste no Supabase
python tests/setup_usuarios_teste.py

# Todos os testes
pytest tests/ -v

# Testes adversariais (sem API key — usa mock)
pytest tests/test_adversarial.py -v

# Testes de integração (requer ANTHROPIC_API_KEY)
pytest tests/test_adversarial.py -v -m integration

# Teste único
pytest tests/test_api.py::TestEndpointDRE::test_admin_acessa_dre -v
```

---

## 14. Roadmap de Fases

| Fase | Descrição | Status |
|---|---|---|
| 1 | Schema inicial, tabelas, RLS, DRE básico | Concluída |
| 2 | Estornos, alertas automáticos, taxa 5% | Concluída |
| 3 | Metas, atingimento, escopos | Concluída |
| 4 | IA com Claude, chat SSE, tool-use loop | Concluída |
| 5 | Repasses, produtores, filtros | Concluída |
| 6 | ETL balancete / importação Excel | Parcial |
| 7 | Módulo lançamentos + configurações (bancos, centros, tipos) | Concluída |
| 8 | Identidade visual MX, landing page, redesign | Concluída |
| 9 | Aprovação de despesas, CRUD usuários, novos schemas | Concluída |
| 10 | (Próximo) CRUD completo metas, gestão usuários frontend, relatórios PDF | Pendente |

---

## Apêndice — Convenções de Código

### Backend

- `async`/`await` em todas as funções de rota e serviço
- Nomes de funções em snake_case
- Todo router segue o padrão:
  ```python
  token = request.headers.get("authorization", "").replace("Bearer ", "")
  db = get_supabase_usuario(token)
  # ... lógica de negócio
  await registrar_auditoria(usuario, "acao", {...}, ip, get_supabase_admin())
  ```
- Valores monetários: sempre `Decimal`, nunca `float`
- Datas no banco: sempre `date` (não `datetime`) para competência

### Frontend

- Funções de formato em `lib/utils.ts` (`formatBRL`, `formatDate`)
- API calls centralizadas em `lib/api.ts` — **nunca** usar `fetch` diretamente nas páginas
- Token sempre obtido via `supabase.auth.getSession()` e passado como parâmetro
- Estados de loading e erro obrigatórios em toda tela com dados assíncronos

### Banco de Dados

- Toda query de negócio usa cliente JWT (`get_supabase_usuario`) — RLS automático
- `get_supabase_admin()` apenas para `audit_log` e operações de sistema
- Funções SQL com `SECURITY INVOKER` — nunca `SECURITY DEFINER` para dados de negócio
- Novas tabelas sempre precisam de políticas RLS antes de ir a produção
