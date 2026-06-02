'use client'
import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useUser } from '@/contexts/UserContext'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import type { Role } from '@/types'

// ── Tipos locais ───────────────────────────────────────────────
interface UsuarioItem { id: string; nome: string; email: string; role: Role; ativo: boolean }
interface BancoItem   { id: string; nome: string; ativo: boolean }
interface CentroItem  { id: string; nome: string; codigo: string; ativo: boolean }
interface TipoItem    { id: string; nome: string; natureza: string; categoria: string | null; custo_tipo: string | null; ativo: boolean }

type Aba = 'usuarios' | 'tipos' | 'bancos' | 'centros'

const inputCls = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700 placeholder-gray-400 focus:border-[#071934] focus:outline-none"
const selectCls = inputCls

// ── Helpers visuais ────────────────────────────────────────────
const ROLE_LABEL: Record<string, string> = { admin: 'Admin', gestor: 'Gestor', contador: 'Contador', comercial: 'Comercial' }
const ROLE_COLOR: Record<string, string> = {
  admin: 'bg-red-50 text-red-700', gestor: 'bg-amber-50 text-amber-700',
  contador: 'bg-blue-50 text-blue-700', comercial: 'bg-gray-100 text-gray-600',
}
const NAT_COLOR: Record<string, string> = {
  despesa: 'bg-red-50 text-red-600', receita: 'bg-green-50 text-green-700',
}

function Chip({ label, cor }: { label: string; cor: string }) {
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${cor}`}>{label}</span>
}
function AtivoChip({ ativo }: { ativo: boolean }) {
  return <Chip label={ativo ? 'Ativo' : 'Inativo'} cor={ativo ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-400'} />
}

// ── Botão toggle ativo/inativo ─────────────────────────────────
function BtnToggle({ ativo, onClick }: { ativo: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`text-xs hover:underline ${ativo ? 'text-gray-400' : 'text-green-600'}`}>
      {ativo ? 'Desativar' : 'Ativar'}
    </button>
  )
}

// ── Seção: Usuários ────────────────────────────────────────────
function SecaoUsuarios({ token, isAdmin }: { token: string; isAdmin: boolean }) {
  const [items, setItems] = useState<UsuarioItem[]>([])
  const [loading, setLoading] = useState(true)
  const [criando, setCriando] = useState(false)
  const [form, setForm] = useState({ nome: '', email: '', senha: '', role: 'comercial' as Role })
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(() => {
    api.get<{ total: number; items: UsuarioItem[] }>('/usuarios', token)
      .then(r => setItems(r.items))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => { carregar() }, [carregar])

  async function criar(e: React.FormEvent) {
    e.preventDefault()
    setCriando(true); setErro(null)
    try {
      await api.post('/usuarios', token, form)
      setForm({ nome: '', email: '', senha: '', role: 'comercial' })
      carregar()
    } catch (err) { setErro(err instanceof Error ? err.message : 'Erro ao criar') }
    finally { setCriando(false) }
  }

  async function toggle(u: UsuarioItem) {
    if (!isAdmin) return
    await api.patch(`/usuarios/${u.id}`, token, { ativo: !u.ativo })
    carregar()
  }

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div className="space-y-5">
      {/* Formulário de criação */}
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Novo Usuário</h3>
        <form onSubmit={criar} className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <input required value={form.nome} onChange={e => set('nome', e.target.value)}
            placeholder="Nome completo" className={inputCls} />
          <input required type="email" value={form.email} onChange={e => set('email', e.target.value)}
            placeholder="E-mail" className={inputCls} />
          <input required type="password" value={form.senha} onChange={e => set('senha', e.target.value)}
            placeholder="Senha" className={inputCls} />
          <select value={form.role} onChange={e => set('role', e.target.value)} className={selectCls}>
            <option value="comercial">Comercial</option>
            <option value="contador">Contador</option>
            <option value="gestor">Gestor</option>
            {isAdmin && <option value="admin">Admin</option>}
          </select>
          <div className="col-span-2 flex items-center gap-3 lg:col-span-4">
            {erro && <p className="text-xs text-red-600">{erro}</p>}
            <button type="submit" disabled={criando}
              className="ml-auto rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-50">
              {criando ? 'Criando…' : '+ Criar Usuário'}
            </button>
          </div>
        </form>
      </div>

      {/* Lista */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        {loading ? (
          <div className="py-10 text-center text-sm text-gray-400">Carregando…</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">E-mail</th>
                <th className="px-4 py-3">Perfil</th>
                <th className="px-4 py-3">Status</th>
                {isAdmin && <th className="px-4 py-3 text-right">Ação</th>}
              </tr>
            </thead>
            <tbody>
              {items.map(u => (
                <tr key={u.id} className="border-t border-gray-50 hover:bg-gray-50">
                  <td className="px-4 py-2.5 font-medium text-gray-800">{u.nome}</td>
                  <td className="px-4 py-2.5 text-gray-500">{u.email}</td>
                  <td className="px-4 py-2.5"><Chip label={ROLE_LABEL[u.role]} cor={ROLE_COLOR[u.role]} /></td>
                  <td className="px-4 py-2.5"><AtivoChip ativo={u.ativo} /></td>
                  {isAdmin && (
                    <td className="px-4 py-2.5 text-right">
                      <BtnToggle ativo={u.ativo} onClick={() => toggle(u)} />
                    </td>
                  )}
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={5} className="py-8 text-center text-sm text-gray-400">Nenhum usuário</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Seção: Tipos de Lançamento ─────────────────────────────────
function SecaoTipos({ token, isAdmin }: { token: string; isAdmin: boolean }) {
  const [items, setItems] = useState<TipoItem[]>([])
  const [loading, setLoading] = useState(true)
  const [criando, setCriando] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ nome: '', natureza: 'despesa', categoria: '', custo_tipo: '' })
  const [editForm, setEditForm] = useState({ nome: '', categoria: '', custo_tipo: '' })
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(() => {
    api.get<TipoItem[]>('/configuracoes/tipos', token)
      .then(setItems)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => { carregar() }, [carregar])

  async function criar(e: React.FormEvent) {
    e.preventDefault()
    setCriando(true); setErro(null)
    try {
      await api.post('/configuracoes/tipos', token, {
        nome: form.nome, natureza: form.natureza,
        categoria: form.categoria || null, custo_tipo: form.custo_tipo || null,
      })
      setForm({ nome: '', natureza: 'despesa', categoria: '', custo_tipo: '' })
      carregar()
    } catch (err) { setErro(err instanceof Error ? err.message : 'Erro') }
    finally { setCriando(false) }
  }

  async function salvarEdicao(id: string) {
    await api.put(`/configuracoes/tipos/${id}`, token, {
      nome: editForm.nome, categoria: editForm.categoria || null, custo_tipo: editForm.custo_tipo || null,
    })
    setEditId(null); carregar()
  }

  async function toggleTipo(t: TipoItem) {
    await api.put(`/configuracoes/tipos/${t.id}`, token, { ativo: !t.ativo })
    carregar()
  }

  function iniciarEdicao(t: TipoItem) {
    setEditId(t.id)
    setEditForm({ nome: t.nome, categoria: t.categoria ?? '', custo_tipo: t.custo_tipo ?? '' })
  }

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const despesas = items.filter(t => t.natureza === 'despesa')
  const receitas = items.filter(t => t.natureza === 'receita')

  return (
    <div className="space-y-5">
      {isAdmin && (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Novo Tipo</h3>
          <form onSubmit={criar} className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <input required value={form.nome} onChange={e => set('nome', e.target.value)}
              placeholder="Nome do tipo" className={inputCls} />
            <select value={form.natureza} onChange={e => set('natureza', e.target.value)} className={selectCls}>
              <option value="despesa">Despesa</option>
              <option value="receita">Receita</option>
            </select>
            <input value={form.categoria} onChange={e => set('categoria', e.target.value)}
              placeholder="Categoria (opcional)" className={inputCls} />
            <select value={form.custo_tipo} onChange={e => set('custo_tipo', e.target.value)} className={selectCls}>
              <option value="">Custo tipo (opcional)</option>
              <option value="fixo">Fixo</option>
              <option value="variavel">Variável</option>
            </select>
            <div className="col-span-2 flex items-center gap-3 lg:col-span-4">
              {erro && <p className="text-xs text-red-600">{erro}</p>}
              <button type="submit" disabled={criando}
                className="ml-auto rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-50">
                {criando ? 'Criando…' : '+ Criar Tipo'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Tabelas por natureza */}
      {[{ label: 'Despesas', cor: 'text-red-600', lista: despesas }, { label: 'Receitas', cor: 'text-green-700', lista: receitas }].map(grupo => (
        <div key={grupo.label} className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <div className="border-b border-gray-100 px-4 py-2.5">
            <h3 className={`text-xs font-semibold uppercase tracking-wide ${grupo.cor}`}>{grupo.label}</h3>
          </div>
          {loading ? (
            <div className="py-6 text-center text-sm text-gray-400">Carregando…</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-medium text-gray-500">
                  <th className="px-4 py-2.5">Nome</th>
                  <th className="px-4 py-2.5">Categoria</th>
                  <th className="px-4 py-2.5">Custo</th>
                  <th className="px-4 py-2.5">Status</th>
                  {isAdmin && <th className="px-4 py-2.5 text-right">Ações</th>}
                </tr>
              </thead>
              <tbody>
                {grupo.lista.map(t => (
                  <tr key={t.id} className="border-t border-gray-50 hover:bg-gray-50">
                    {editId === t.id ? (
                      <>
                        <td className="px-4 py-1.5">
                          <input value={editForm.nome} onChange={e => setEditForm(f => ({ ...f, nome: e.target.value }))}
                            className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:outline-none" />
                        </td>
                        <td className="px-4 py-1.5">
                          <input value={editForm.categoria} onChange={e => setEditForm(f => ({ ...f, categoria: e.target.value }))}
                            className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:outline-none" placeholder="Categoria" />
                        </td>
                        <td className="px-4 py-1.5">
                          <select value={editForm.custo_tipo} onChange={e => setEditForm(f => ({ ...f, custo_tipo: e.target.value }))}
                            className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:outline-none">
                            <option value="">—</option>
                            <option value="fixo">Fixo</option>
                            <option value="variavel">Variável</option>
                          </select>
                        </td>
                        <td />
                        <td className="px-4 py-1.5 text-right">
                          <span className="inline-flex gap-2">
                            <button onClick={() => salvarEdicao(t.id)} className="text-xs font-medium text-green-600 hover:underline">Salvar</button>
                            <button onClick={() => setEditId(null)} className="text-xs text-gray-400 hover:underline">Cancelar</button>
                          </span>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-4 py-2.5 font-medium text-gray-800">{t.nome}</td>
                        <td className="px-4 py-2.5 text-gray-500">{t.categoria ?? '—'}</td>
                        <td className="px-4 py-2.5 capitalize text-gray-500">{t.custo_tipo ?? '—'}</td>
                        <td className="px-4 py-2.5"><AtivoChip ativo={t.ativo} /></td>
                        {isAdmin && (
                          <td className="px-4 py-2.5 text-right">
                            <span className="inline-flex gap-3">
                              <button onClick={() => iniciarEdicao(t)} className="text-xs text-blue-500 hover:underline">Editar</button>
                              <BtnToggle ativo={t.ativo} onClick={() => toggleTipo(t)} />
                            </span>
                          </td>
                        )}
                      </>
                    )}
                  </tr>
                ))}
                {grupo.lista.length === 0 && (
                  <tr><td colSpan={5} className="py-6 text-center text-sm text-gray-400">Nenhum tipo cadastrado</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Seção: Bancos ──────────────────────────────────────────────
function SecaoBancos({ token, isAdmin }: { token: string; isAdmin: boolean }) {
  const [items, setItems] = useState<BancoItem[]>([])
  const [loading, setLoading] = useState(true)
  const [criando, setCriando] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [nome, setNome] = useState('')
  const [editNome, setEditNome] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(() => {
    api.get<BancoItem[]>('/configuracoes/bancos', token)
      .then(setItems).catch(() => {}).finally(() => setLoading(false))
  }, [token])

  useEffect(() => { carregar() }, [carregar])

  async function criar(e: React.FormEvent) {
    e.preventDefault()
    setCriando(true); setErro(null)
    try {
      await api.post('/configuracoes/bancos', token, { nome })
      setNome(''); carregar()
    } catch (err) { setErro(err instanceof Error ? err.message : 'Erro') }
    finally { setCriando(false) }
  }

  async function salvarEdicao(id: string) {
    await api.put(`/configuracoes/bancos/${id}`, token, { nome: editNome })
    setEditId(null); carregar()
  }

  async function toggleBanco(b: BancoItem) {
    await api.put(`/configuracoes/bancos/${b.id}`, token, { ativo: !b.ativo })
    carregar()
  }

  return (
    <div className="space-y-5">
      {isAdmin && (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Novo Banco</h3>
          <form onSubmit={criar} className="flex gap-3">
            <input required value={nome} onChange={e => setNome(e.target.value)}
              placeholder="Nome do banco" className={`${inputCls} flex-1`} />
            {erro && <p className="self-center text-xs text-red-600">{erro}</p>}
            <button type="submit" disabled={criando}
              className="rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-50 whitespace-nowrap">
              {criando ? 'Criando…' : '+ Criar Banco'}
            </button>
          </form>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        {loading ? (
          <div className="py-10 text-center text-sm text-gray-400">Carregando…</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">Status</th>
                {isAdmin && <th className="px-4 py-3 text-right">Ações</th>}
              </tr>
            </thead>
            <tbody>
              {items.map(b => (
                <tr key={b.id} className="border-t border-gray-50 hover:bg-gray-50">
                  {editId === b.id ? (
                    <>
                      <td className="px-4 py-1.5">
                        <input value={editNome} onChange={e => setEditNome(e.target.value)}
                          className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:outline-none" />
                      </td>
                      <td />
                      <td className="px-4 py-1.5 text-right">
                        <span className="inline-flex gap-2">
                          <button onClick={() => salvarEdicao(b.id)} className="text-xs font-medium text-green-600 hover:underline">Salvar</button>
                          <button onClick={() => setEditId(null)} className="text-xs text-gray-400 hover:underline">Cancelar</button>
                        </span>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-4 py-2.5 font-medium text-gray-800">{b.nome}</td>
                      <td className="px-4 py-2.5"><AtivoChip ativo={b.ativo} /></td>
                      {isAdmin && (
                        <td className="px-4 py-2.5 text-right">
                          <span className="inline-flex gap-3">
                            <button onClick={() => { setEditId(b.id); setEditNome(b.nome) }}
                              className="text-xs text-blue-500 hover:underline">Editar</button>
                            <BtnToggle ativo={b.ativo} onClick={() => toggleBanco(b)} />
                          </span>
                        </td>
                      )}
                    </>
                  )}
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={3} className="py-8 text-center text-sm text-gray-400">Nenhum banco cadastrado</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Seção: Centros de Custo ────────────────────────────────────
function SecaoCentros({ token, isAdmin }: { token: string; isAdmin: boolean }) {
  const [items, setItems] = useState<CentroItem[]>([])
  const [loading, setLoading] = useState(true)
  const [criando, setCriando] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ nome: '', codigo: '' })
  const [editNome, setEditNome] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(() => {
    api.get<CentroItem[]>('/configuracoes/centros-custo', token)
      .then(setItems).catch(() => {}).finally(() => setLoading(false))
  }, [token])

  useEffect(() => { carregar() }, [carregar])

  async function criar(e: React.FormEvent) {
    e.preventDefault()
    setCriando(true); setErro(null)
    try {
      await api.post('/configuracoes/centros-custo', token, form)
      setForm({ nome: '', codigo: '' }); carregar()
    } catch (err) { setErro(err instanceof Error ? err.message : 'Erro') }
    finally { setCriando(false) }
  }

  async function salvarEdicao(id: string) {
    await api.put(`/configuracoes/centros-custo/${id}`, token, { nome: editNome })
    setEditId(null); carregar()
  }

  async function toggleCentro(c: CentroItem) {
    await api.put(`/configuracoes/centros-custo/${c.id}`, token, { ativo: !c.ativo })
    carregar()
  }

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div className="space-y-5">
      {isAdmin && (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Novo Centro de Custo</h3>
          <form onSubmit={criar} className="flex gap-3">
            <input required value={form.nome} onChange={e => set('nome', e.target.value)}
              placeholder="Nome" className={`${inputCls} flex-1`} />
            <input required value={form.codigo} onChange={e => set('codigo', e.target.value)}
              placeholder="Código" className={`${inputCls} w-36`} />
            {erro && <p className="self-center text-xs text-red-600">{erro}</p>}
            <button type="submit" disabled={criando}
              className="rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-50 whitespace-nowrap">
              {criando ? 'Criando…' : '+ Criar Centro'}
            </button>
          </form>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        {loading ? (
          <div className="py-10 text-center text-sm text-gray-400">Carregando…</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Status</th>
                {isAdmin && <th className="px-4 py-3 text-right">Ações</th>}
              </tr>
            </thead>
            <tbody>
              {items.map(c => (
                <tr key={c.id} className="border-t border-gray-50 hover:bg-gray-50">
                  {editId === c.id ? (
                    <>
                      <td className="px-4 py-1.5">
                        <input value={editNome} onChange={e => setEditNome(e.target.value)}
                          className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:outline-none" />
                      </td>
                      <td className="px-4 py-1.5 text-gray-500">{c.codigo}</td>
                      <td />
                      <td className="px-4 py-1.5 text-right">
                        <span className="inline-flex gap-2">
                          <button onClick={() => salvarEdicao(c.id)} className="text-xs font-medium text-green-600 hover:underline">Salvar</button>
                          <button onClick={() => setEditId(null)} className="text-xs text-gray-400 hover:underline">Cancelar</button>
                        </span>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-4 py-2.5 font-medium text-gray-800">{c.nome}</td>
                      <td className="px-4 py-2.5 text-gray-500">{c.codigo}</td>
                      <td className="px-4 py-2.5"><AtivoChip ativo={c.ativo} /></td>
                      {isAdmin && (
                        <td className="px-4 py-2.5 text-right">
                          <span className="inline-flex gap-3">
                            <button onClick={() => { setEditId(c.id); setEditNome(c.nome) }}
                              className="text-xs text-blue-500 hover:underline">Editar</button>
                            <BtnToggle ativo={c.ativo} onClick={() => toggleCentro(c)} />
                          </span>
                        </td>
                      )}
                    </>
                  )}
                </tr>
              ))}
              {items.length === 0 && (
                <tr><td colSpan={4} className="py-8 text-center text-sm text-gray-400">Nenhum centro cadastrado</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── Página principal ───────────────────────────────────────────
const ABAS: { id: Aba; label: string; desc: string }[] = [
  { id: 'usuarios', label: 'Usuários',             desc: 'Gerencie os acessos ao sistema' },
  { id: 'tipos',    label: 'Tipos de Lançamento',  desc: 'Categorias de despesas e receitas' },
  { id: 'bancos',   label: 'Bancos',               desc: 'Contas bancárias da corretora' },
  { id: 'centros',  label: 'Centros de Custo',     desc: 'Unidades e filiais' },
]

export default function ConfiguracoesPage() {
  const { token } = useAuth()
  const { role } = useUser()
  const isAdmin = role === 'admin'
  const [aba, setAba] = useState<Aba>('usuarios')

  if (!token) return null

  const abaAtual = ABAS.find(a => a.id === aba)!

  return (
    <div className="space-y-5">
      {/* Cabeçalho */}
      <div>
        <h1 className="text-2xl font-bold text-[#071934]">Configurações</h1>
        <p className="mt-0.5 text-sm text-gray-500">Gerencie os parâmetros do sistema</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl border border-gray-200 bg-white p-1 shadow-sm">
        {ABAS.map(a => (
          <button
            key={a.id}
            onClick={() => setAba(a.id)}
            className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              aba === a.id
                ? 'bg-[#071934] text-white shadow-sm'
                : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>

      {/* Subtítulo da aba ativa */}
      <p className="text-xs text-gray-400">{abaAtual.desc}</p>

      {/* Conteúdo da aba */}
      {aba === 'usuarios' && <SecaoUsuarios token={token} isAdmin={isAdmin} />}
      {aba === 'tipos'    && <SecaoTipos    token={token} isAdmin={isAdmin} />}
      {aba === 'bancos'   && <SecaoBancos   token={token} isAdmin={isAdmin} />}
      {aba === 'centros'  && <SecaoCentros  token={token} isAdmin={isAdmin} />}
    </div>
  )
}
