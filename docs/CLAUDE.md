# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the backend locally
uvicorn app.main:app --reload --port 8000

# Install dependencies
pip install -r requirements.txt

# Run all tests (requires Supabase credentials and pre-created test users)
pytest tests/ -v

# Run a single test file
pytest tests/test_api.py -v

# Run a single test class
pytest tests/test_api.py::TestEndpointMetas -v

# Run a single test
pytest tests/test_api.py::TestEndpointDRE::test_admin_acessa_dre -v

# Run adversarial tests (no API key needed — mocks Anthropic)
pytest tests/test_adversarial.py -v

# Run integration tests (requires ANTHROPIC_API_KEY)
pytest tests/test_adversarial.py -v -m integration

# Create test users in Supabase before running tests
python tests/setup_usuarios_teste.py
```

Swagger UI is available at `http://localhost:8000/docs` when running locally.

## Architecture

### Stack
- **Backend**: FastAPI + Python 3.12, `async`/`await` throughout
- **Database/Auth**: Supabase (PostgreSQL + PostgREST + Supabase Auth)
- **AI layer**: Anthropic Claude (`claude-sonnet-4-5`), streaming via SSE
- **ORM**: None — direct Supabase client (`supabase-py`) using PostgREST

### Two-layer security model

Security is enforced at **two independent layers**:

1. **FastAPI layer** (`app/auth.py`): Every request validates the Supabase JWT by calling `admin.auth.get_user(token)`. After validation, the user's `role` is fetched fresh from `usuarios` table (never from the JWT itself). Role-checks use `_exigir_roles()` dependencies or inline checks in routers.

2. **Database layer (RLS)**: All business queries use `get_supabase_usuario(jwt_token)` which passes the user's JWT to PostgREST. Supabase applies Row-Level Security policies automatically. Helper SQL functions (`get_meu_role()`, `get_minha_equipe()`, `get_meu_produtor()`) power the RLS policies.

`get_supabase_admin()` bypasses RLS — use it **only** for audit logging and admin-only system operations (never for fetching user-facing data).

### Four roles and their access matrix

| Perfil | DRE | Comissões | Estornos | Metas | Repasses | Lançamentos | Config |
|---|---|---|---|---|---|---|---|
| **admin** | Completo | Todos | Todos | Todas | Todos | R/W/D | R/W/D |
| **gestor** | Sem despesas/EBITDA | Equipe | Todos | Globais+equipe+produtores | Todos | — | — |
| **comercial** | Sem receita líquida | Próprias | Todos | Apenas própria | Todos | — | — |
| **contador** | Completo | Todos | Todos | Todas | Todos | R/W | — |

### Router pattern

Every router follows this pattern:
```python
token = request.headers.get("authorization", "").replace("Bearer ", "")
db = get_supabase_usuario(token)  # RLS client
# ... use db for business queries
await registrar_auditoria(usuario, "acao", {...}, ip, get_supabase_admin())
```

Routers are in `app/routers/`. Services in `app/services/`. All monetary values use `Decimal`, never `float`.

### AI tool-use loop (`app/ai/orchestrator.py`)

The chat endpoint streams SSE events. The loop:
1. Sends user question + system prompt + available tools for the user's role to Claude
2. If `stop_reason == "tool_use"`: validates tool permission, executes via `executar_tool()`, appends result, loops
3. Capped at **20 iterations** to prevent exfiltration loops
4. Audit-logs the full conversation (truncated at 500/2000 chars)

Tools available per role are defined in `app/ai/tools.py` via `PERMISSOES_TOOL` dict and `tools_para_perfil()`. The LLM **never calculates** DRE — all numbers come from deterministic SQL functions (`dre_por_periodo`, `atingimento_metas`, etc.) in `migrations/0003_functions.sql`.

### Database migrations

Migrations are in `migrations/` numbered `0001–0005`:
- `0001_init.sql` — all tables (equipes, produtores, usuarios, apolices, comissoes, repasses, estornos, despesas, impostos, metas, audit_log)
- `0002_rls.sql` — RLS policies + helper functions (`get_meu_role`, `get_minha_equipe`, `get_meu_produtor`)
- `0003_functions.sql` — SQL functions called via RPC (`dre_por_periodo`, `atingimento_metas`, `receita_por_ramo`, `taxa_estorno`, `comissoes_por_produtor`)
- `0004_seed.sql` — test data
- `0005_financeiro.sql` — bancos, centros_custo, tipos_lancamento, receitas_outras tables + updated `dre_por_periodo` that includes `receitas_outras`

`TODAS_AS_MIGRATIONS.sql` is a concatenated version of all migrations. `executar_migrations.py` runs them via psycopg2 (requires `DATABASE_URL`).

### Environment variables (`.env`)

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=          # from Supabase dashboard > Settings > API > JWT Settings
DATABASE_URL=                 # optional, only needed for running migrations directly
ANTHROPIC_API_KEY=
ENVIRONMENT=development       # set to "production" to enable prod guards
```

Tests also look for `.env.test` (overrides `.env`). Test credentials use `@mxseguros.test` domain; test users must exist in Supabase before running `pytest` (run `python tests/setup_usuarios_teste.py` first).

### Key design decisions

- **Role from DB, not JWT**: `_buscar_role_no_banco()` is called on every request. This ensures revoked/changed roles take effect immediately without token expiry.
- **`SECURITY INVOKER` on SQL functions**: RLS applies inside functions — users can't access data they shouldn't even via RPC.
- **`categoria` field on `despesas`**: Legacy ENUM field (`despesa_categoria`) coexists with newer `tipo_lancamento_id` FK. The DRE function handles both paths. New code should prefer `tipo_lancamento_id`.
- **Metas `metrica` field**: The schema defines `numero_apolices` as a valid metric, but `atingimento_metas()` always sums `comissoes.valor` (monetary). This is an existing inconsistency — if implementing `numero_apolices`, the SQL function must be updated to COUNT apólices instead.
