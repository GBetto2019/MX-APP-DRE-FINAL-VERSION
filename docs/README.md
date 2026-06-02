# MX Seguros — DRE-IA

Sistema de Demonstração do Resultado do Exercício com Inteligência Artificial para a **MX Seguros**.

---

## Visão Geral

| Camada       | Tecnologia                      |
|--------------|----------------------------------|
| Backend      | Python 3.12 + FastAPI            |
| Banco de dados | Supabase (PostgreSQL + RLS)    |
| IA           | Anthropic Claude (claude-sonnet-4-5) |
| Frontend     | Next.js 15 (App Router) + Tailwind |
| Autenticação | Supabase Auth (ES256 JWT)        |
| ETL          | pandas + openpyxl                |

---

## Estrutura do Repositório

```
MX/
├── DRE_APP/                    # Backend FastAPI
│   ├── app/
│   │   ├── ai/                 # Camada de IA (tools, orchestrator, prompts)
│   │   ├── models/             # Schemas Pydantic
│   │   ├── routers/            # Endpoints FastAPI
│   │   ├── services/           # Lógica de negócio
│   │   ├── auth.py             # JWT Supabase Auth
│   │   ├── config.py           # Variáveis de ambiente
│   │   ├── database.py         # Clientes Supabase
│   │   └── main.py             # Ponto de entrada
│   ├── etl/                    # Importação de balancetes Excel
│   ├── migrations/             # SQL: schema, RLS, funções, seed
│   └── tests/                  # 87 testes (RLS + API + adversarial)
├── frontend/                   # Next.js 15
│   ├── app/                    # App Router (login, dashboard, chat)
│   ├── components/             # DRE, Estornos, Metas, Repasses, Chat
│   └── lib/                    # Supabase client/server, API, utils
└── README.md
```

---

## Como Rodar Localmente

### Backend

```bash
cd DRE_APP

# 1. Instalar dependências
pip install -r requirements.txt

# 2. Criar .env (nunca commitar)
cp .env.example .env
# Preencher: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
#            ANTHROPIC_API_KEY

# 3. Rodar migrações (cole TODAS_AS_MIGRATIONS.sql no Supabase SQL Editor)

# 4. Iniciar servidor
uvicorn app.main:app --reload --port 8000

# 5. Rodar testes
pytest tests/ -v
```

### Frontend

```bash
cd frontend

# 1. Instalar dependências
npm install

# 2. Criar .env.local
cp .env.local.example .env.local
# Preencher: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY

# 3. Iniciar servidor de desenvolvimento
npm run dev
# http://localhost:3000

# 4. Build de produção
npm run build
```

---

## Perfis de Acesso

| Perfil      | DRE visível                                                    |
|-------------|----------------------------------------------------------------|
| **Admin**   | Todos os campos + todas as tools de IA                         |
| **Contador**| Todos os campos financeiros                                    |
| **Gestor**  | Até margem de contribuição (sem despesas fixas / EBITDA)       |
| **Comercial**| Apenas receita bruta, estornos, repasses do próprio produtor  |

Regra de ouro: **o perfil vem sempre do banco de dados** (tabela `usuarios`) — nunca do JWT nem do prompt.

---

## Segurança

- **RLS** (Row-Level Security) ativo em todas as tabelas sensíveis
- **SECURITY INVOKER** em todas as funções SQL (RLS sempre aplicada)
- **Audit log** append-only: toda interação com a IA é registrada
- **Limite de 20 iterações** de tool_use (evita loops e exfiltração)
- **30 testes adversariais** com jailbreak, role escalation, prompt injection, data exfiltration
- Dados sensíveis truncados no log (máx. 2000 chars, sem salários em plaintext)
- `ANTHROPIC_API_KEY` nunca exposta no frontend (só `ANON_KEY` é pública)

---

## ETL — Importação de Balancetes

```bash
cd DRE_APP
python etl/import_balancete.py  # gera revisar.csv com lançamentos pendentes
```

O ETL classifica automaticamente ~99,7% dos lançamentos por palavras-chave. Lançamentos não reconhecidos ficam em `revisar.csv` para revisão manual.

---

## Endpoints da API

| Método | Rota          | Descrição                         |
|--------|---------------|-----------------------------------|
| GET    | `/health`     | Health check                      |
| GET    | `/dre`        | DRE por período (filtrado por role)|
| GET    | `/dre/ramos`  | Receita por ramo                  |
| GET    | `/comissoes`  | Comissões por período             |
| GET    | `/estornos`   | Estornos por período              |
| GET    | `/metas`      | Metas por competência             |
| GET    | `/repasses`   | Repasses (comercial vê só o próprio)|
| POST   | `/chat`       | Chat com IA (streaming SSE)       |

Todos os endpoints requerem `Authorization: Bearer <JWT>`.
Swagger: http://localhost:8000/docs

---

## Variáveis de Ambiente

### Backend (`.env`)

```
SUPABASE_URL=https://SEU_PROJECT.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
SUPABASE_JWT_SECRET=          # opcional; fallback usa service_role_key
DATABASE_URL=                 # opcional; para asyncpg direto
ANTHROPIC_API_KEY=sk-ant-...
ENVIRONMENT=development       # ou production
SECRET_KEY=                   # JWT interno (gerar com: openssl rand -hex 32)
```

### Frontend (`.env.local`)

```
NEXT_PUBLIC_SUPABASE_URL=https://SEU_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> ⚠️ Nunca commitar `.env` ou `.env.local` — ambos estão no `.gitignore`.

---

## Testes

```bash
# Backend — todos os testes
cd DRE_APP
pytest tests/ -v

# Apenas testes de RLS (requer conexão Supabase)
pytest tests/test_rls.py -v

# Apenas testes de API
pytest tests/test_api.py -v

# Apenas testes adversariais (sem API Anthropic — usa mock)
pytest tests/test_adversarial.py -v
```

Cobertura atual: **87 testes passando**.

---

## Deploy em Produção

1. **Supabase**: rodar `TODAS_AS_MIGRATIONS.sql` no SQL Editor
2. **Backend**: deploy em Railway, Render ou VPS com Docker
   - Configurar variáveis de ambiente
   - `ENVIRONMENT=production` ativa logs INFO e oculta detalhes de erro
3. **Frontend**: deploy na Vercel (integração nativa Next.js)
   - Configurar `NEXT_PUBLIC_*` nas env vars do projeto Vercel
   - `NEXT_PUBLIC_API_URL` → URL de produção do backend

---

MX Seguros © 2026
