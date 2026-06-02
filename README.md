# MX Seguros — DRE-IA

Sistema de **Demonstração do Resultado do Exercício com Inteligência Artificial** para a MX Corretora de Seguros.

Gestão financeira em tempo real com controle de acesso por perfil, chat com IA, exportação de relatórios e ETL de balancetes.

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.12 + FastAPI |
| Banco de dados | Supabase (PostgreSQL + RLS + PostgREST) |
| IA | Anthropic Claude (`claude-sonnet-4-5`) — streaming SSE |
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |
| Autenticação | Supabase Auth (JWT ES256) |
| ETL | pandas + openpyxl |
| Testes | pytest — 272 testes passando |
| CI/CD | GitHub Actions |

---

## Funcionalidades

- **DRE em tempo real** — cálculo determinístico via funções SQL, com snapshot para períodos fechados
- **Assistente IA** — chat com streaming SSE, contexto financeiro por perfil, histórico persistido
- **Lançamentos** — CRUD de despesas e receitas com aprovação por fluxo (pendente → aprovada)
- **Exportações** — DRE em PDF (ReportLab) e Excel (openpyxl) respeitando o perfil do usuário
- **ETL** — importação de balancetes Excel com categorização automática (~99,7% de cobertura)
- **Multi-tenant** — isolamento completo por tenant via RLS
- **Audit log** — toda interação registrada (append-only), rotação automática a cada 90 dias

---

## Perfis de Acesso

| Perfil | DRE | Comissões | Estornos | Metas | Lançamentos |
|--------|-----|-----------|----------|-------|-------------|
| **admin** | Completo | Todas | Todos | Todas | R/W/D |
| **contador** | Completo | Todas | Todos | Todas | R/W |
| **gestor** | Sem despesas/EBITDA | Equipe | Equipe | Globais + equipe | — |
| **comercial** | Sem receita líquida | Próprias | Próprios | Própria | — |

> O perfil é sempre lido do banco de dados — nunca do JWT nem do input do usuário.

---

## Estrutura do Projeto

```
├── app/
│   ├── ai/                  # Orchestrator, tools, system prompt
│   ├── middleware/           # Rate limit, período, tenant, limites
│   ├── models/              # Schemas Pydantic
│   ├── routers/             # 14 routers FastAPI
│   ├── services/            # Lógica de negócio
│   ├── auth.py              # Validação JWT + cache de role (TTL 60s)
│   ├── database.py          # asyncpg pool + clientes Supabase
│   └── main.py              # Ponto de entrada
├── frontend/
│   ├── public/              # Logos MX
│   └── src/
│       ├── app/             # Rotas Next.js (App Router)
│       │   ├── login/
│       │   └── dashboard/   # Visão Geral, DRE, Lançamentos, Estornos,
│       │                    # Metas, Repasses, Assistente IA, Exportações
│       ├── components/      # Sidebar, ErrorBoundary, Skeleton, Badge
│       ├── hooks/           # useAuth
│       ├── lib/             # api.ts, supabase.ts, utils.ts
│       └── types/           # Interfaces TypeScript
├── migrations/              # 0001–0019 (schema, RLS, funções, multi-tenant)
├── tests/                   # 272 testes (API, RLS, adversarial, sprints 0–7)
├── etl/                     # import_balancete.py, categorizacao.py
├── scripts/                 # criar_usuario.py, health_check.py
├── docs/                    # SDD v3, plano de sprints, documentação
└── .github/workflows/       # CI/CD (lint + testes + build)
```

---

## Pré-requisitos

- Python 3.12+
- Node.js 20+
- Conta [Supabase](https://supabase.com) com projeto criado
- Chave API [Anthropic](https://console.anthropic.com)

---

## Instalação e Execução Local

### 1. Clonar o repositório

```bash
git clone https://github.com/GBetto2019/MX-APP-DRE-FINAL-VERSION.git
cd MX-APP-DRE-FINAL-VERSION
```

### 2. Configurar variáveis de ambiente

**Backend** — copiar e preencher:
```bash
cp .env.example .env
```

```env
SUPABASE_URL=https://SEU_PROJETO.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
DATABASE_URL=postgresql://postgres:SENHA@db.SEU_PROJETO.supabase.co:5432/postgres
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=gere_com_openssl_rand_hex_32
ENVIRONMENT=development
```

**Frontend** — criar `frontend/.env.local`:
```env
NEXT_PUBLIC_SUPABASE_URL=https://SEU_PROJETO.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Aplicar migrations no Supabase

Acesse o **SQL Editor** do seu projeto Supabase e execute o arquivo:
```
migrations/TODAS_AS_MIGRATIONS.sql
```

Ou aplique individualmente na ordem `0001 → 0019`.

### 4. Instalar dependências e subir o backend

```bash
pip install -r docs/requirements.txt
pip install slowapi structlog reportlab

uvicorn app.main:app --reload --port 8000
# Swagger: http://localhost:8000/docs
```

### 5. Instalar dependências e subir o frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

---

## Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check público |
| GET | `/dashboard` | DRE + metas + alertas (uma chamada) |
| GET | `/dre` | DRE por período |
| GET | `/comissoes` | Comissões por período |
| GET | `/estornos` | Estornos com taxa de alerta |
| GET | `/metas` | Metas e atingimento |
| GET | `/repasses` | Repasses a produtores |
| GET/POST/DELETE | `/lancamentos/despesas` | CRUD de despesas |
| GET/POST/DELETE | `/lancamentos/receitas` | CRUD de receitas manuais |
| GET/POST | `/fechamentos` | Fechamento mensal (trava período) |
| POST | `/importacao/balancete` | Upload + preview ETL |
| GET | `/exports/dre/xlsx` | Export Excel |
| GET | `/exports/dre/pdf` | Export PDF |
| GET/POST/PATCH | `/usuarios` | Gestão de usuários (admin) |
| GET | `/usuarios/me` | Perfil do usuário autenticado |
| GET/POST | `/chat/stream` | Chat IA com streaming SSE |

Todos os endpoints (exceto `/health`) requerem `Authorization: Bearer <JWT>`.

---

## Testes

```bash
# Todos os testes (272)
pytest tests/ -v

# Por suite
pytest tests/test_api.py -v          # endpoints e autenticação
pytest tests/test_rls.py -v          # Row-Level Security
pytest tests/test_adversarial.py -v  # segurança IA (sem API key — usa mock)

# Sprints específicos
pytest tests/test_sprint0_seguranca.py -v
pytest tests/test_sprint2_seguranca.py -v
pytest tests/test_sprint4_5_6_multitenant.py -v

# Criar usuários de teste antes de rodar RLS
python tests/setup_usuarios_teste.py
```

---

## CI/CD

O workflow `.github/workflows/ci.yml` executa em todo PR:

1. **Backend** — `ruff check` + `pytest tests/test_adversarial.py`
2. **Frontend** — `tsc --noEmit` + `npm run build`

Para ativar, cadastre os secrets em **Settings → Secrets → Actions**:

| Secret | Descrição |
|--------|-----------|
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_ANON_KEY` | Chave anônima |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role (nunca expor no frontend) |
| `ANTHROPIC_API_KEY` | Chave da API Anthropic |
| `DATABASE_URL` | URL direta do PostgreSQL |

---

## Segurança

- **Dupla camada**: FastAPI (JWT) + PostgreSQL (RLS) independentes
- **Role do banco**: perfil lido da tabela `usuarios` a cada request (nunca do JWT)
- **SECURITY INVOKER** em todas as funções SQL — RLS sempre aplicada
- **Soft-delete** em despesas: campo `status = 'excluida'`, nunca DELETE físico
- **Rate limiting**: `/chat` 10/min, `/dre` e `/dashboard` 30/min, demais 60/min
- **30 testes adversariais**: jailbreak, role escalation, prompt injection, exfiltração de dados
- **Loop cap**: máximo 20 iterações de tool_use por requisição de chat
- `.env` e `.env.local` no `.gitignore` — credenciais nunca commitadas

---

## Deploy em Produção

### Backend (Railway / Render / VPS)
```bash
ENVIRONMENT=production  # ativa HSTS, logs JSON, oculta stack traces
```

### Frontend (Vercel)
1. Importar repositório na Vercel
2. Definir variáveis `NEXT_PUBLIC_*` nas configurações do projeto
3. `NEXT_PUBLIC_API_URL` → URL pública do backend

### Banco de dados
- Todas as migrations já aplicadas via `migrations/TODAS_AS_MIGRATIONS.sql`
- Backup automático via Supabase (plano Pro recomendado em produção)

---

## ETL — Importação de Balancetes

```bash
# Via script (local)
python etl/import_balancete.py

# Via API (frontend)
POST /importacao/balancete        # upload + preview
POST /importacao/balancete/confirmar  # efetivar importação
```

O ETL classifica automaticamente os lançamentos por palavras-chave. Itens não reconhecidos vão para `data/output/revisar.csv`.

---

## Licença

Uso interno MX Corretora de Seguros © 2026. Todos os direitos reservados.
