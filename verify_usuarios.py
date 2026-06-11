import asyncio, httpx, re, time, os

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://jrqmntvmtukmhlmnukgn.supabase.co')
ANON_KEY     = os.environ.get('SUPABASE_ANON_KEY', '')
SERVICE_KEY  = os.environ.get('SUPABASE_SERVICE_KEY', '')
API          = os.environ.get('API_URL', 'https://alert-patience-production-86b7.up.railway.app')

async def get_token(email):
    async with httpx.AsyncClient(follow_redirects=False) as c:
        r = await c.post(f'{SUPABASE_URL}/auth/v1/admin/generate_link',
            json={'type': 'magiclink', 'email': email},
            headers={'apikey': SERVICE_KEY, 'Authorization': f'Bearer {SERVICE_KEY}'}, timeout=10)
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

async def main():
    ts = int(time.time())

    token_gestor  = await get_token('gestor@mxseguros.test')
    token_admin   = await get_token('admin@mxseguros.test')
    token_contador = await get_token('contador@mxseguros.test')
    token_comercial = await get_token('comercial@mxseguros.test')

    hg = {'Authorization': f'Bearer {token_gestor}'}
    ha = {'Authorization': f'Bearer {token_admin}'}
    hc = {'Authorization': f'Bearer {token_contador}'}
    hco = {'Authorization': f'Bearer {token_comercial}'}

    async with httpx.AsyncClient(timeout=15) as c:

        print('=== CRUD Usuarios pelo GESTOR ===')

        r = await c.post(f'{API}/usuarios', headers=hg, json={
            'nome': f'Teste Gestor {ts}',
            'email': f'teste_gestor_{ts}@mxseguros.test',
            'senha': 'Senha@123456',
            'role': 'admin',
        })
        p(r.status_code == 201, 'Gestor cria usuario role=admin', f'{r.status_code}')
        novo_id = r.json().get('id') if r.status_code == 201 else None

        if novo_id:
            r2 = await c.patch(f'{API}/usuarios/{novo_id}', headers=hg,
                               json={'nome': f'Editado {ts}', 'role': 'contador'})
            nome_ok = r2.json().get('nome') == f'Editado {ts}' if r2.status_code == 200 else False
            p(r2.status_code == 200 and nome_ok, 'Gestor edita nome e role do usuario',
              f'{r2.status_code} nome_ok={nome_ok}')

            r3 = await c.delete(f'{API}/usuarios/{novo_id}', headers=hg)
            p(r3.status_code == 204, 'Gestor desativa usuario (soft delete)', str(r3.status_code))

        print()
        print('=== CRUD Usuarios pelo ADMIN ===')

        r = await c.post(f'{API}/usuarios', headers=ha, json={
            'nome': f'Teste Admin {ts}',
            'email': f'teste_admin_{ts}@mxseguros.test',
            'senha': 'Senha@123456',
            'role': 'gestor',
        })
        p(r.status_code == 201, 'Admin cria usuario role=gestor', str(r.status_code))
        novo_id2 = r.json().get('id') if r.status_code == 201 else None

        if novo_id2:
            r2 = await c.patch(f'{API}/usuarios/{novo_id2}', headers=ha,
                               json={'role': 'comercial'})
            p(r2.status_code == 200, 'Admin edita role do usuario', str(r2.status_code))

            r3 = await c.delete(f'{API}/usuarios/{novo_id2}', headers=ha)
            p(r3.status_code == 204, 'Admin desativa usuario', str(r3.status_code))

        print()
        print('=== Contador e Comercial NAO podem gerenciar usuarios ===')

        for lbl, hdr in [('contador', hc), ('comercial', hco)]:
            r = await c.post(f'{API}/usuarios', headers=hdr, json={
                'nome': 'Nao deve', 'email': f'nd_{ts}@x.com',
                'senha': 'x', 'role': 'comercial',
            })
            p(r.status_code == 403, f'{lbl} nao pode criar usuario', str(r.status_code))

            r = await c.get(f'{API}/usuarios', headers=hdr)
            p(r.status_code == 403, f'{lbl} nao pode listar usuarios', str(r.status_code))

    passed = sum(1 for s, _ in results if s == 'PASS')
    failed = sum(1 for s, _ in results if s == 'FAIL')
    print(f'\n{"="*50}')
    print(f'RESULTADO: {passed} PASS / {failed} FAIL')
    if failed == 0:
        print('Tudo OK!')
    print('='*50)

asyncio.run(main())
