#!/usr/bin/env python3
"""
MX Seguros — DRE-IA | Cria usuário no Supabase Auth + perfil na tabela usuarios.

Uso:
    python scripts/criar_usuario.py --email joao@mxseguros.com --senha Senha@123 --role gestor
    python scripts/criar_usuario.py --email ana@mxseguros.com  --senha Senha@123 --role comercial --produtor-id UUID
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROLES_VALIDOS = ["admin", "gestor", "comercial", "contador"]


def main():
    parser = argparse.ArgumentParser(description="Cria usuário MX Seguros")
    parser.add_argument("--email", required=True)
    parser.add_argument("--senha", required=True)
    parser.add_argument("--role", required=True, choices=ROLES_VALIDOS)
    parser.add_argument("--equipe-id", default=None, help="UUID da equipe (gestor)")
    parser.add_argument("--produtor-id", default=None, help="UUID do produtor (comercial)")
    args = parser.parse_args()

    from app.database import get_supabase_admin

    admin = get_supabase_admin()

    print(f"Criando usuário: {args.email} | role: {args.role}")

    # 1. Cria no Supabase Auth
    try:
        resp = admin.auth.admin.create_user({
            "email": args.email,
            "password": args.senha,
            "email_confirm": True,
        })
        user_id = resp.user.id
        print(f"  [OK]  Auth criado: {user_id}")
    except Exception as e:
        print(f"  [ERRO] Falha no Auth: {e}")
        sys.exit(1)

    # 2. Insere perfil na tabela usuarios
    try:
        dados = {
            "id":          user_id,
            "email":       args.email,
            "role":        args.role,
            "equipe_id":   args.equipe_id,
            "produtor_id": args.produtor_id,
            "ativo":       True,
        }
        admin.table("usuarios").insert(dados).execute()
        print(f"  [OK]  Perfil inserido na tabela usuarios")
    except Exception as e:
        print(f"  [ERRO] Falha ao inserir perfil: {e}")
        # Rollback: deleta o usuário do Auth
        try:
            admin.auth.admin.delete_user(user_id)
            print("  [OK]  Rollback: usuário Auth removido")
        except Exception:
            pass
        sys.exit(1)

    print(f"\nUsuário criado com sucesso!")
    print(f"  email:       {args.email}")
    print(f"  role:        {args.role}")
    print(f"  user_id:     {user_id}")
    if args.equipe_id:
        print(f"  equipe_id:   {args.equipe_id}")
    if args.produtor_id:
        print(f"  produtor_id: {args.produtor_id}")


if __name__ == "__main__":
    main()
