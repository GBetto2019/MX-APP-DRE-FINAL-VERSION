"""
MX Seguros — DRE-IA
Testes de Row-Level Security (RLS) — Fase 1, critério de aceite obrigatório.

Valida que cada perfil só acessa os dados que tem permissão.
Matriz de permissões: §4.5 do ESCOPO_DRE_IA_CORRETORA.md

Execute:
    pytest tests/test_rls.py -v

Pré-requisito:
    python tests/setup_usuarios_teste.py  (cria usuários e .env.test)
"""
from __future__ import annotations

import os
import uuid
import pytest
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega .env (service role) e .env.test (UIDs de teste)
load_dotenv()
load_dotenv(".env.test", override=False)

SUPABASE_URL     = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

SENHAS = {
    "admin":     ("admin@mxseguros.test",     "Teste@123"),
    "gestor":    ("gestor@mxseguros.test",    "Teste@123"),
    "comercial": ("comercial@mxseguros.test", "Teste@123"),
    "contador":  ("contador@mxseguros.test",  "Teste@123"),
}


# ── FIXTURES ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def admin_client() -> Client:
    """Cliente com service_role — bypassa RLS (usado para seed de teste)."""
    return create_client(SUPABASE_URL, SERVICE_ROLE_KEY)


@pytest.fixture(scope="session")
def clientes_por_role(admin_client: Client) -> dict[str, Client]:
    """
    Retorna um cliente Supabase autenticado para cada role.
    Cada cliente tem o JWT do usuário, então RLS é aplicado normalmente.
    """
    clientes: dict[str, Client] = {}
    for role, (email, senha) in SENHAS.items():
        c = create_client(SUPABASE_URL, os.environ["SUPABASE_ANON_KEY"])
        resp = c.auth.sign_in_with_password({"email": email, "password": senha})
        assert resp.user is not None, f"Login falhou para {role}: {email}"
        clientes[role] = c
    return clientes


@pytest.fixture(scope="session")
def dados_teste(admin_client: Client) -> dict:
    """
    Insere dados mínimos para os testes de RLS usando service_role.
    Retorna os IDs criados para referência nos testes.
    """
    # Busca IDs base
    equipe_matriz = admin_client.table("equipes") \
        .select("id").eq("unidade", "matriz").limit(1).execute()
    equipe_id = equipe_matriz.data[0]["id"] if equipe_matriz.data else None

    seguradora = admin_client.table("seguradoras") \
        .select("id").limit(1).execute()
    seguradora_id = seguradora.data[0]["id"] if seguradora.data else None

    ramo = admin_client.table("ramos") \
        .select("id").limit(1).execute()
    ramo_id = ramo.data[0]["id"] if ramo.data else None

    # Busca produtor do comercial de teste
    comercial_user = admin_client.table("usuarios") \
        .select("produtor_id").eq("role", "comercial").limit(1).execute()
    produtor_comercial_id = comercial_user.data[0]["produtor_id"] \
        if comercial_user.data else None

    # Cria um segundo produtor (de outra equipe — comercial NÃO deve ver)
    outro_produtor = admin_client.table("produtores").insert({
        "nome": "Produtor Outro",
        "tipo": "interno",
        "ativo": True,
    }).execute()
    outro_produtor_id = outro_produtor.data[0]["id"] if outro_produtor.data else None

    # Cria cliente de seguro
    cliente = admin_client.table("clientes").insert({
        "nome": "Cliente Teste RLS",
        "tipo": "pf",
    }).execute()
    cliente_id = cliente.data[0]["id"] if cliente.data else None

    # Apólice do comercial de teste (ele PODE ver)
    apolice_propria = admin_client.table("apolices").insert({
        "numero":          f"TEST-{uuid.uuid4().hex[:8].upper()}",
        "seguradora_id":   seguradora_id,
        "ramo_id":         ramo_id,
        "cliente_id":      cliente_id,
        "produtor_id":     produtor_comercial_id,
        "equipe_id":       equipe_id,
        "premio_total":    1000.00,
        "inicio_vigencia": "2026-01-01",
        "fim_vigencia":    "2027-01-01",
        "emitida_em":      "2026-01-01",
    }).execute()
    apolice_propria_id = apolice_propria.data[0]["id"] if apolice_propria.data else None

    # Apólice de outro produtor (comercial NÃO deve ver)
    apolice_alheia = admin_client.table("apolices").insert({
        "numero":          f"TEST-{uuid.uuid4().hex[:8].upper()}",
        "seguradora_id":   seguradora_id,
        "ramo_id":         ramo_id,
        "cliente_id":      cliente_id,
        "produtor_id":     outro_produtor_id,
        "premio_total":    2000.00,
        "inicio_vigencia": "2026-01-01",
        "fim_vigencia":    "2027-01-01",
        "emitida_em":      "2026-01-01",
    }).execute()
    apolice_alheia_id = apolice_alheia.data[0]["id"] if apolice_alheia.data else None

    # Comissão da apólice própria
    comissao_propria = admin_client.table("comissoes").insert({
        "apolice_id":  apolice_propria_id,
        "tipo":        "comissao_padrao",
        "valor":       150.00,
        "competencia": "2026-01-01",
    }).execute()

    # Comissão da apólice alheia
    comissao_alheia = admin_client.table("comissoes").insert({
        "apolice_id":  apolice_alheia_id,
        "tipo":        "comissao_padrao",
        "valor":       300.00,
        "competencia": "2026-01-01",
    }).execute()

    # Despesa (somente admin/contador devem ver)
    despesa = admin_client.table("despesas").insert({
        "categoria":     "pessoal",
        "subcategoria":  "salario",
        "descricao":     "Salario teste RLS",
        "valor":         5000.00,
        "competencia":   "2026-01-01",
        "centro_custo":  "matriz",
    }).execute()

    return {
        "equipe_id":              equipe_id,
        "produtor_comercial_id":  produtor_comercial_id,
        "outro_produtor_id":      outro_produtor_id,
        "apolice_propria_id":     apolice_propria_id,
        "apolice_alheia_id":      apolice_alheia_id,
        "comissao_propria_id":    comissao_propria.data[0]["id"] if comissao_propria.data else None,
        "comissao_alheia_id":     comissao_alheia.data[0]["id"] if comissao_alheia.data else None,
        "despesa_id":             despesa.data[0]["id"] if despesa.data else None,
    }


# ── TESTES: APOLICES ──────────────────────────────────────────

class TestApolicesRLS:

    def test_admin_ve_todas_apolices(self, clientes_por_role, dados_teste):
        """Admin deve ver todas as apólices, incluindo as de outros produtores."""
        c = clientes_por_role["admin"]
        resp = c.table("apolices").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["apolice_propria_id"] in ids
        assert dados_teste["apolice_alheia_id"] in ids

    def test_comercial_ve_apenas_proprias_apolices(self, clientes_por_role, dados_teste):
        """Comercial deve ver apenas apólices do seu produtor_id."""
        c = clientes_por_role["comercial"]
        resp = c.table("apolices").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["apolice_propria_id"] in ids
        assert dados_teste["apolice_alheia_id"] not in ids, \
            "FALHA DE SEGURANCA: comercial viu apolice de outro produtor!"

    def test_gestor_ve_apolices_da_equipe(self, clientes_por_role, dados_teste):
        """Gestor deve ver apólices da sua equipe."""
        c = clientes_por_role["gestor"]
        resp = c.table("apolices").select("id").execute()
        ids = {r["id"] for r in resp.data}
        # Apólice própria está na equipe do gestor
        assert dados_teste["apolice_propria_id"] in ids

    def test_contador_ve_todas_apolices(self, clientes_por_role, dados_teste):
        """Contador tem visão completa para fins contábeis."""
        c = clientes_por_role["contador"]
        resp = c.table("apolices").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["apolice_propria_id"] in ids
        assert dados_teste["apolice_alheia_id"] in ids


# ── TESTES: COMISSOES ─────────────────────────────────────────

class TestComissoesRLS:

    def test_admin_ve_todas_comissoes(self, clientes_por_role, dados_teste):
        """Admin vê todas as comissões."""
        c = clientes_por_role["admin"]
        resp = c.table("comissoes").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["comissao_propria_id"] in ids
        assert dados_teste["comissao_alheia_id"] in ids

    def test_comercial_nao_ve_comissoes_alheias(self, clientes_por_role, dados_teste):
        """CRÍTICO: Comercial NÃO deve ver comissões de outros produtores."""
        c = clientes_por_role["comercial"]
        resp = c.table("comissoes").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["comissao_alheia_id"] not in ids, \
            "FALHA CRITICA DE SEGURANCA: comercial viu comissao de outro produtor!"

    def test_comercial_ve_proprias_comissoes(self, clientes_por_role, dados_teste):
        """Comercial deve ver suas próprias comissões."""
        c = clientes_por_role["comercial"]
        resp = c.table("comissoes").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["comissao_propria_id"] in ids

    def test_gestor_ve_comissoes_da_equipe(self, clientes_por_role, dados_teste):
        """Gestor vê comissões das apólices da sua equipe."""
        c = clientes_por_role["gestor"]
        resp = c.table("comissoes").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["comissao_propria_id"] in ids

    def test_contador_ve_todas_comissoes(self, clientes_por_role, dados_teste):
        """Contador vê todas as comissões."""
        c = clientes_por_role["contador"]
        resp = c.table("comissoes").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["comissao_propria_id"] in ids
        assert dados_teste["comissao_alheia_id"] in ids


# ── TESTES: DESPESAS ──────────────────────────────────────────

class TestDespesasRLS:

    def test_admin_ve_despesas(self, clientes_por_role, dados_teste):
        """Admin vê todas as despesas."""
        c = clientes_por_role["admin"]
        resp = c.table("despesas").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["despesa_id"] in ids

    def test_gestor_nao_ve_despesas(self, clientes_por_role, dados_teste):
        """CRÍTICO: Gestor NÃO deve ver despesas (salários, pró-labore etc.)."""
        c = clientes_por_role["gestor"]
        resp = c.table("despesas").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["despesa_id"] not in ids, \
            "FALHA DE SEGURANCA: gestor viu despesas!"

    def test_comercial_nao_ve_despesas(self, clientes_por_role, dados_teste):
        """CRÍTICO: Comercial NÃO deve ver despesas."""
        c = clientes_por_role["comercial"]
        resp = c.table("despesas").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["despesa_id"] not in ids, \
            "FALHA CRITICA: comercial viu despesas!"

    def test_contador_ve_despesas(self, clientes_por_role, dados_teste):
        """Contador tem acesso completo às despesas."""
        c = clientes_por_role["contador"]
        resp = c.table("despesas").select("id").execute()
        ids = {r["id"] for r in resp.data}
        assert dados_teste["despesa_id"] in ids


# ── TESTES: USUARIOS ──────────────────────────────────────────

class TestUsuariosRLS:

    def test_comercial_ve_apenas_proprio_perfil(self, clientes_por_role):
        """Comercial só deve ver o próprio registro em usuarios."""
        c = clientes_por_role["comercial"]
        resp = c.table("usuarios").select("email").execute()
        emails = {r["email"] for r in resp.data}
        assert "admin@mxseguros.test" not in emails, \
            "FALHA: comercial viu dados do admin!"
        assert "comercial@mxseguros.test" in emails

    def test_admin_ve_todos_usuarios(self, clientes_por_role):
        """Admin vê todos os usuários."""
        c = clientes_por_role["admin"]
        resp = c.table("usuarios").select("email").execute()
        emails = {r["email"] for r in resp.data}
        assert "admin@mxseguros.test" in emails
        assert "comercial@mxseguros.test" in emails
        assert "gestor@mxseguros.test" in emails


# ── TESTES: FUNÇÕES SQL ───────────────────────────────────────

class TestFuncoesSQLRLS:

    def test_admin_dre_retorna_dados(self, clientes_por_role):
        """Admin consegue chamar dre_por_periodo e recebe JSON válido."""
        c = clientes_por_role["admin"]
        resp = c.rpc("dre_por_periodo", {
            "p_inicio": "2026-01-01",
            "p_fim":    "2026-12-31",
        }).execute()
        assert resp.data is not None
        assert "receita_bruta" in resp.data
        assert "ebitda" in resp.data

    def test_comercial_dre_retorna_apenas_proprios_dados(self, clientes_por_role, dados_teste):
        """
        Comercial chama dre_por_periodo mas RLS filtra:
        receita_bruta deve ser menor que a do admin (não inclui dados alheios).
        """
        admin_resp = clientes_por_role["admin"].rpc("dre_por_periodo", {
            "p_inicio": "2026-01-01",
            "p_fim":    "2026-12-31",
        }).execute()

        comercial_resp = clientes_por_role["comercial"].rpc("dre_por_periodo", {
            "p_inicio": "2026-01-01",
            "p_fim":    "2026-12-31",
        }).execute()

        receita_admin     = float(admin_resp.data["receita_bruta"])
        receita_comercial = float(comercial_resp.data["receita_bruta"])

        # Comercial só vê as próprias comissões (R$ 150), admin vê tudo (R$ 450+)
        assert receita_comercial <= receita_admin, \
            "FALHA: comercial viu receita maior que admin (impossível com RLS correto)"
        assert receita_comercial < receita_admin, \
            "FALHA DE SEGURANCA: comercial viu a mesma receita que o admin!"

    def test_taxa_estorno_retorna_alerta(self, clientes_por_role):
        """Função taxa_estorno retorna estrutura correta."""
        c = clientes_por_role["admin"]
        resp = c.rpc("taxa_estorno", {
            "p_inicio": "2026-01-01",
            "p_fim":    "2026-12-31",
        }).execute()
        assert resp.data is not None
        assert "taxa_percentual" in resp.data
        assert "alerta_5pct" in resp.data
