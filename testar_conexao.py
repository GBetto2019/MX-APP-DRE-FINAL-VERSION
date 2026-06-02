"""
Teste de conexao com o Supabase — MX Seguros DRE-IA.
Execute: python testar_conexao.py
"""
from __future__ import annotations

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def testar_cliente(nome: str, key: str) -> None:
    print(f"\n--- {nome} ---")
    print(f"  Key: {key[:20]}...")
    try:
        cliente: Client = create_client(SUPABASE_URL, key)
        print("  [OK] Cliente criado!")
        response = cliente.auth.get_session()
        sessao = response.session if response else None
        print(f"  [OK] Auth respondeu | Sessao: {sessao or 'nenhuma (normal)'}")
    except Exception as e:
        print(f"  [ERRO] {e}")
        raise


def testar_conexao() -> None:
    print("=" * 50)
    print("  Teste de conexao - MX Seguros Supabase")
    print("=" * 50)
    print(f"  URL: {SUPABASE_URL}")

    testar_cliente("anon key (frontend)", SUPABASE_ANON_KEY)
    testar_cliente("service_role key (backend)", SUPABASE_SERVICE_KEY)

    print("\n[SUCESSO] Ambas as chaves conectadas ao Supabase!")


if __name__ == "__main__":
    testar_conexao()
