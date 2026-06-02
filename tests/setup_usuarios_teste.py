"""
MX Seguros — DRE-IA
Cria os 4 usuários de teste no Supabase Auth e popula a tabela usuarios.

Execute UMA VEZ antes de rodar os testes:
    python tests/setup_usuarios_teste.py

Usuários criados:
    admin@mxseguros.test      / Teste@123
    gestor@mxseguros.test     / Teste@123
    comercial@mxseguros.test  / Teste@123
    contador@mxseguros.test   / Teste@123
"""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL     = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

USUARIOS_TESTE = [
    {
        "email":    "admin@mxseguros.test",
        "senha":    "Teste@123",
        "nome":     "Admin Teste",
        "role":     "admin",
    },
    {
        "email":    "gestor@mxseguros.test",
        "senha":    "Teste@123",
        "nome":     "Gestor Teste",
        "role":     "gestor",
    },
    {
        "email":    "comercial@mxseguros.test",
        "senha":    "Teste@123",
        "nome":     "Comercial Teste",
        "role":     "comercial",
    },
    {
        "email":    "contador@mxseguros.test",
        "senha":    "Teste@123",
        "nome":     "Contador Teste",
        "role":     "contador",
    },
]


def main() -> None:
    print("=" * 55)
    print("  MX Seguros — Setup de usuarios de teste")
    print("=" * 55)

    # Cliente com service_role bypassa confirmacao de email
    admin_client: Client = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

    ids_criados: dict[str, str] = {}

    for usuario in USUARIOS_TESTE:
        print(f"\n  Criando: {usuario['email']} ({usuario['role']})")

        # 1. Cria no Supabase Auth
        try:
            resp = admin_client.auth.admin.create_user({
                "email":          usuario["email"],
                "password":       usuario["senha"],
                "email_confirm":  True,   # confirma automaticamente
            })
            uid = resp.user.id
            print(f"    [OK] Auth criado | UID: {uid}")
        except Exception as e:
            if "already been registered" in str(e) or "already exists" in str(e):
                # Busca o UID existente
                lista = admin_client.auth.admin.list_users()
                uid = next(
                    u.id for u in lista
                    if u.email == usuario["email"]
                )
                print(f"    [JA EXISTE] UID: {uid}")
            else:
                print(f"    [ERRO] {e}")
                sys.exit(1)

        ids_criados[usuario["role"]] = uid

        # 2. Insere/atualiza na tabela publica usuarios
        try:
            admin_client.table("usuarios").upsert({
                "id":    uid,
                "nome":  usuario["nome"],
                "email": usuario["email"],
                "role":  usuario["role"],
                "ativo": True,
            }).execute()
            print(f"    [OK] Tabela usuarios atualizada")
        except Exception as e:
            print(f"    [ERRO] Tabela usuarios: {e}")
            sys.exit(1)

    # Vincula gestor e comercial a uma equipe existente
    print("\n  Vinculando gestor e comercial a equipe...")
    try:
        equipe = admin_client.table("equipes") \
            .select("id") \
            .eq("unidade", "matriz") \
            .limit(1) \
            .execute()

        if equipe.data:
            equipe_id = equipe.data[0]["id"]

            # Atualiza gestor com equipe_id
            admin_client.table("usuarios") \
                .update({"equipe_id": equipe_id}) \
                .eq("role", "gestor") \
                .execute()

            # Cria um produtor para o usuario comercial
            produtor = admin_client.table("produtores").upsert({
                "nome":      "Comercial Teste",
                "tipo":      "interno",
                "equipe_id": equipe_id,
                "ativo":     True,
            }).execute()

            if produtor.data:
                produtor_id = produtor.data[0]["id"]
                admin_client.table("usuarios") \
                    .update({
                        "equipe_id":   equipe_id,
                        "produtor_id": produtor_id,
                    }) \
                    .eq("role", "comercial") \
                    .execute()
                print("    [OK] Gestor e Comercial vinculados a equipe Matriz")

    except Exception as e:
        print(f"    [AVISO] Vinculo de equipe: {e}")

    # Salva os IDs para os testes
    _salvar_ids(ids_criados)

    print()
    print("=" * 55)
    print("  [SUCESSO] Usuarios de teste prontos!")
    print()
    print("  Credenciais:")
    for u in USUARIOS_TESTE:
        print(f"    {u['role']:10s}  {u['email']}  /  {u['senha']}")
    print()
    print("  Execute agora:")
    print("    pytest tests/test_rls.py -v")
    print("=" * 55)


def _salvar_ids(ids: dict[str, str]) -> None:
    """Salva os UIDs em .env.test para uso nos testes."""
    linhas = ["# UIDs dos usuarios de teste — gerado automaticamente\n"]
    for role, uid in ids.items():
        linhas.append(f"TEST_UID_{role.upper()}={uid}\n")

    caminho = ".env.test"
    with open(caminho, "w", encoding="utf-8") as f:
        f.writelines(linhas)
    print(f"\n  [OK] UIDs salvos em {caminho}")


if __name__ == "__main__":
    main()
