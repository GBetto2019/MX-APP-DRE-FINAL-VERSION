import asyncio, httpx, os, re, time

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://jrqmntvmtukmhlmnukgn.supabase.co')
ANON_KEY     = os.environ.get('SUPABASE_ANON_KEY', '')
SERVICE_KEY  = os.environ.get('SUPABASE_SERVICE_KEY', '')
API          = os.environ.get('API_URL', 'https://alert-patience-production-86b7.up.railway.app')

async def get_token(email):
    async with httpx.AsyncClient(follow_redirects=False) as c:
        r = await c.post(
            f'{SUPABASE_URL}/auth/v1/admin/generate_link',
            json={'type': 'magiclink', 'email': email},
            headers={'apikey': SERVICE_KEY, 'Authorization': f'Bearer {SERVICE_KEY}'},
            timeout=10
        )
        link = r.json().get('action_link', '')
        if not link:
            return None
        r2 = await c.get(link, headers={'apikey': ANON_KEY}, timeout=10)
        loc = r2.headers.get('location', '')
        m = re.search(r'access_token=([^&]+)', loc)
        return m.group(1) if m else None

results = []

def p(ok, label, detail=''):
    sym = 'PASS' if ok else 'FAIL'
    results.append((sym, label))
    print(f'  {sym}  {label}' + (f' | {detail}' if detail else ''))
    return ok

async def main():
    ts    = int(time.time())
    today = time.strftime('%Y-%m')
    inicio = today + '-01'
    fim    = today + '-30'
    periodo = {'inicio': inicio, 'fim': fim}

    print('=== Obtendo tokens ===')
    tokens = {}
    for email in ['admin@mxseguros.test','gestor@mxseguros.test','contador@mxseguros.test','comercial@mxseguros.test']:
        t = await get_token(email)
        role = email.split('@')[0]
        tokens[role] = t
        p(bool(t), f'token {role}')

    def hdr(role):
        return {'Authorization': f'Bearer {tokens[role]}'}

    async with httpx.AsyncClient(timeout=15) as c:

        # ── Health ────────────────────────────────────────────
        print('\n=== Health ===')
        r = await c.get(f'{API}/health')
        ver = r.json().get('version') if r.status_code == 200 else 'err'
        p(r.status_code == 200 and ver == '1.2.1', 'GET /health version=1.2.1', ver)

        # ── /usuarios/me ──────────────────────────────────────
        print('\n=== /usuarios/me (permissions) ===')
        for role in ['admin','gestor','contador','comercial']:
            r = await c.get(f'{API}/usuarios/me', headers=hdr(role))
            data = r.json() if r.status_code == 200 else {}
            perms = data.get('permissions')
            p(r.status_code == 200, f'GET /usuarios/me [{role}]',
              'permissions=custom' if perms else 'permissions=null(padrao role)')

        # ── DRE: campos por role ──────────────────────────────
        print('\n=== DRE: campos por role ===')
        for role in ['admin','gestor','contador','comercial']:
            r = await c.get(f'{API}/dre', headers=hdr(role), params=periodo)
            if r.status_code == 200:
                d   = r.json().get('dre', {})
                rb  = d.get('receita_bruta') is not None
                df  = d.get('despesas_fixas') is not None
                rl  = d.get('resultado_liquido') is not None
                if role == 'comercial':
                    p(rb and not df and not rl, f'GET /dre [{role}] campos restritos', f'rb={rb} df={df} rl={rl}')
                else:
                    p(rb and df and rl, f'GET /dre [{role}] campos completos', f'rb={rb} df={df} rl={rl}')
            else:
                p(False, f'GET /dre [{role}]', str(r.status_code))

        # ── Lancamentos/despesas ──────────────────────────────
        print('\n=== Lancamentos/despesas: acesso por role ===')
        for role, exp in [('admin',200),('gestor',200),('contador',200),('comercial',403)]:
            r = await c.get(f'{API}/lancamentos/despesas', headers=hdr(role), params=periodo)
            p(r.status_code == exp, f'GET /lancamentos/despesas [{role}]', f'{r.status_code} (esperado {exp})')

        # ── Aprovacoes (pendentes) ────────────────────────────
        # Aprovações = despesas pendentes; todos exceto comercial podem ver despesas
        print('\n=== Aprovacoes: despesas pendentes por role ===')
        for role, exp in [('admin',200),('gestor',200),('contador',200),('comercial',403)]:
            r = await c.get(f'{API}/lancamentos/despesas', headers=hdr(role), params={**periodo, 'status': 'pendente'})
            p(r.status_code == exp, f'GET despesas pendentes [{role}]', f'{r.status_code} (esperado {exp})')

        # ── Aprovar despesa (acao) ─────────────────────────────
        print('\n=== Aprovar despesa: acao por role ===')
        r = await c.get(f'{API}/lancamentos/despesas', headers=hdr('admin'), params={**periodo, 'status': 'pendente'})
        pendentes = r.json().get('items', []) if r.status_code == 200 else []
        if pendentes:
            despesa_id = pendentes[0]['id']
            for role, exp in [('admin',200),('gestor',200),('contador',403),('comercial',403)]:
                r2 = await c.patch(f'{API}/lancamentos/despesas/{despesa_id}/aprovar', headers=hdr(role))
                p(r2.status_code == exp, f'PATCH aprovar despesa [{role}]', f'{r2.status_code} (esperado {exp})')
        else:
            print('  SKIP  aprovar despesa | sem despesas pendentes')

        # ── Fechamentos ───────────────────────────────────────
        print('\n=== Fechamentos: acesso por role ===')
        for role, exp in [('admin',200),('gestor',200),('contador',200),('comercial',403)]:
            r = await c.get(f'{API}/fechamentos', headers=hdr(role))
            p(r.status_code == exp, f'GET /fechamentos [{role}]', f'{r.status_code} (esperado {exp})')

        # ── Configuracoes escrita ─────────────────────────────
        print('\n=== Configuracoes escrita - bancos ===')
        for role, exp in [('admin',201),('gestor',201),('contador',403),('comercial',403)]:
            r = await c.post(f'{API}/configuracoes/bancos', headers=hdr(role),
                             json={'nome': f'Verify {ts} {role}'})
            p(r.status_code == exp, f'POST /configuracoes/bancos [{role}]', f'{r.status_code} (esperado {exp})')

        print('\n=== Configuracoes escrita - tipos ===')
        for role, exp in [('admin',201),('gestor',201),('contador',403),('comercial',403)]:
            r = await c.post(f'{API}/configuracoes/tipos', headers=hdr(role),
                             json={'nome': f'Tipo Verify {ts} {role}', 'natureza': 'despesa'})
            p(r.status_code == exp, f'POST /configuracoes/tipos [{role}]', f'{r.status_code} (esperado {exp})')

        print('\n=== Configuracoes escrita - centros-custo ===')
        for role, exp in [('admin',201),('gestor',201),('contador',403),('comercial',403)]:
            r = await c.post(f'{API}/configuracoes/centros-custo', headers=hdr(role),
                             json={'nome': f'Centro Verify {ts} {role}', 'codigo': f'V{role[:2].upper()}{ts}'})
            p(r.status_code == exp, f'POST /configuracoes/centros-custo [{role}]', f'{r.status_code} (esperado {exp})')

        # ── Usuarios ──────────────────────────────────────────
        print('\n=== Usuarios: listagem por role ===')
        for role, exp in [('admin',200),('gestor',200),('contador',403),('comercial',403)]:
            r = await c.get(f'{API}/usuarios', headers=hdr(role))
            p(r.status_code == exp, f'GET /usuarios [{role}]', f'{r.status_code} (esperado {exp})')

        # ── Status inicial de despesas por role ───────────────
        print('\n=== Despesas: status_inicial por role ===')
        r = await c.get(f'{API}/configuracoes/tipos', headers=hdr('admin'), params={'natureza': 'despesa'})
        tipos_desp = r.json() if r.status_code == 200 else []
        if tipos_desp:
            tipo_id = tipos_desp[0]['id']
            # comercial pode criar despesas (status pendente); admin/gestor criam aprovada
            for role, exp_st in [('admin','aprovada'),('gestor','aprovada'),('comercial','pendente')]:
                r2 = await c.post(f'{API}/lancamentos/despesas', headers=hdr(role), json={
                    'subcategoria': 'Teste verify', 'descricao': f'Verify {ts}',
                    'valor': 1.0, 'competencia': inicio,
                    'tipo_lancamento_id': tipo_id
                })
                if r2.status_code in (200, 201):
                    st = r2.json().get('status')
                    p(st == exp_st, f'POST despesa [{role}] status={st}', f'esperado={exp_st}')
                else:
                    p(False, f'POST despesa [{role}]', f'{r2.status_code}: {r2.text[:100]}')

    passed = sum(1 for s, _ in results if s == 'PASS')
    failed = sum(1 for s, _ in results if s == 'FAIL')
    print(f'\n{"="*50}')
    print(f'RESULTADO FINAL: {passed} PASS / {failed} FAIL')
    if failed == 0:
        print('Tudo OK!')
    print('='*50)

asyncio.run(main())
