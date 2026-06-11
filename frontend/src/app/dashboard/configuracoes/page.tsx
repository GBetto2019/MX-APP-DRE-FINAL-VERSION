'use client'
import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useUser } from '@/contexts/UserContext'
import { api } from '@/lib/api'
import type { Role, Permissions } from '@/types'
import { getDefaultPermissions } from '@/types'

// ── Tipos locais ───────────────────────────────────────────────
interface UsuarioItem { id: string; nome: string; email: string; role: Role; ativo: boolean; permissions?: Permissions | null }
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

function Chip({ label, cor }: { label: string; cor: string }) {
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${cor}`}>{label}</span>
}
function AtivoChip({ ativo }: { ativo: boolean }) {
  return <Chip label={ativo ? 'Ativo' : 'Inativo'} cor={ativo ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-400'} />
}
function BtnExcluir({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="text-xs text-red-500 hover:text-red-700 hover:underline">
      Excluir
    </button>
  )
}

// ── Configuração de telas e ações para os checkboxes ──────────
const TELAS_CONFIG: Array<{
  id: keyof Permissions
  label: string
  acoes: Array<{ key: string; label: string }>
}> = [
  { id: 'visao_geral',   label: 'Visão Geral',   acoes: [{ key: 'visualizar', label: 'Ver' }] },
  { id: 'dre',           label: 'DRE',            acoes: [{ key: 'visualizar', label: 'Ver' }] },
  { id: 'lancamentos',   label: 'Lançamentos',    acoes: [
    { key: 'visualizar', label: 'Ver' },
    { key: 'criar',      label: 'Criar' },
    { key: 'editar',     label: 'Editar' },
    { key: 'deletar',    label: 'Deletar' },
  ]},
  { id: 'aprovacoes',    label: 'Aprovações',     acoes: [
    { key: 'visualizar', label: 'Ver' },
    { key: 'aprovar',    label: 'Aprovar' },
  ]},
  { id: 'assistente',    label: 'Assistente IA',  acoes: [{ key: 'visualizar', label: 'Ver' }] },
  { id: 'configuracoes', label: 'Configurações',  acoes: [
    { key: 'visualizar', label: 'Ver' },
    { key: 'criar',      label: 'Criar' },
    { key: 'editar',     label: 'Editar' },
    { key: 'deletar',    label: 'Deletar' },
  ]},
]

// ── Componente de checkboxes de permissão ──────────────────────
function PermissoesSelector({
  permissions,
  onChange,
}: {
  permissions: Permissions
  onChange: (p: Permissions) => void
}) {
  function toggle(tela: keyof Permissions, acao: string) {
    const current = (permissions[tela] as Record<string, boolean>)[acao] ?? false
    onChange({
      ...permissions,
      [tela]: { ...permissions[tela], [acao]: !current },
    })
  }

  return (
    <div className="col-span-1 sm:col-span-2 lg:col-span-4 rounded-lg border border-gray-200 bg-white overflow-hidden">
      <div className="border-b border-gray-100 px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Permissões de Acesso</p>
      </div>
      <div className="divide-y divide-gray-50">
        {TELAS_CONFIG.map(tela => (
          <div key={tela.id} className="flex items-center gap-3 px-3 py-2">
            <span className="w-28 shrink-0 text-xs font-medium text-gray-700">{tela.label}</span>
            <div className="flex flex-wrap gap-3">
              {tela.acoes.map(acao => {
                const checked = (permissions[tela.id] as Record<string, boolean>)?.[acao.key] ?? false
                return (
                  <label key={acao.key} className="flex cursor-pointer items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(tela.id, acao.key)}
                      className="h-3.5 w-3.5 cursor-pointer rounded border-gray-300 text-[#071934] focus:ring-[#071934]"
                    />
                    <span className="text-xs text-gray-600">{acao.label}</span>
                  </label>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Modal de edição de usuário ─────────────────────────────────
function ModalEdicaoUsuario({
  usuario,
  token,
  onSalvo,
  onFechar,
}: {
  usuario: UsuarioItem
  token: string
  onSalvo: () => void
  onFechar: () => void
}) {
  const [form, setForm] = useState({
    nome:        usuario.nome,
    role:        usuario.role,
    permissions: (usuario.permissions as Permissions) ?? getDefaultPermissions(usuario.role),
  })
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    setSalvando(true); setErro(null)
    try {
      await api.patch(`/usuarios/${usuario.id}`, token, {
        nome:        form.nome,
        role:        form.role,
        permissions: form.permissions,
      })
      onSalvo()
    } catch (err) { setErro(err instanceof Error ? err.message : 'Erro ao salvar') }
    finally { setSalvando(false) }
  }

  function handleRoleChange(newRole: Role) {
    setForm(f => ({ ...f, role: newRole, permissions: getDefaultPermissions(newRole) }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h2 className="text-sm font-semibold text-gray-800">Editar Usuário</h2>
          <button onClick={onFechar} className="text-gray-400 hover:text-gray-600">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <form onSubmit={salvar} className="space-y-4 p-5">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">E-mail</label>
            <p className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500">{usuario.email}</p>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Nome</label>
            <input required value={form.nome} onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} className={inputCls} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Perfil</label>
            <select value={form.role} onChange={e => handleRoleChange(e.target.value as Role)} className={selectCls}>
              <option value="comercial">Comercial</option>
              <option value="contador">Contador</option>
              <option value="gestor">Gestor</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Permissões de Acesso</label>
            <PermissoesSelector permissions={form.permissions} onChange={p => setForm(f => ({ ...f, permissions: p }))} />
          </div>
          {erro && <p className="text-xs text-red-600">{erro}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onFechar}
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={salvando}
              className="rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-50">
              {salvando ? 'Salvando…' : 'Salvar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Seção: Usuários ────────────────────────────────────────────
function SecaoUsuarios({ token, role, podeExcluir }: { token: string; role: Role; podeExcluir: boolean }) {
  const isAdminOuGestor = role === 'admin' || role === 'gestor'

  const [items, setItems] = useState<UsuarioItem[]>([])
  const [loading, setLoading] = useState(true)
  const [criando, setCriando] = useState(false)
  const [editandoUsuario, setEditandoUsuario] = useState<UsuarioItem | null>(null)
  const [confirmExcluir, setConfirmExcluir] = useState<UsuarioItem | null>(null)
  const [form, setForm] = useState({
    nome: '', email: '', senha: '', role: 'comercial' as Role,
    permissions: getDefaultPermissions('comercial'),
  })
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
      await api.post('/usuarios', token, {
        nome: form.nome, email: form.email, senha: form.senha,
        role: form.role, permissions: form.permissions,
      })
      setForm({ nome: '', email: '', senha: '', role: 'comercial', permissions: getDefaultPermissions('comercial') })
      carregar()
    } catch (err) { setErro(err instanceof Error ? err.message : 'Erro ao criar') }
    finally { setCriando(false) }
  }

  async function excluir(u: UsuarioItem) {
    await api.delete(`/usuarios/${u.id}`, token)
    setConfirmExcluir(null)
    carregar()
  }

  function handleRoleChange(newRole: Role) {
    setForm(f => ({ ...f, role: newRole, permissions: getDefaultPermissions(newRole) }))
  }

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  return (
    <>
      {editandoUsuario && (
        <ModalEdicaoUsuario
          usuario={editandoUsuario}
          token={token}
          onSalvo={() => { setEditandoUsuario(null); carregar() }}
          onFechar={() => setEditandoUsuario(null)}
        />
      )}

      {confirmExcluir && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="mb-2 text-sm font-semibold text-gray-800">Excluir usuário?</h3>
            <p className="mb-5 text-sm text-gray-500">
              <strong>{confirmExcluir.nome}</strong> será excluído permanentemente e não poderá mais acessar o sistema.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmExcluir(null)}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
                Cancelar
              </button>
              <button onClick={() => excluir(confirmExcluir)}
                className="rounded-lg bg-red-600 px-5 py-2 text-sm font-medium text-white hover:bg-red-700">
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-5">
        {isAdminOuGestor && (
          <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Novo Usuário</h3>
            <form onSubmit={criar} className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <input required value={form.nome} onChange={e => set('nome', e.target.value)}
                placeholder="Nome completo" className={inputCls} />
              <input required type="email" value={form.email} onChange={e => set('email', e.target.value)}
                placeholder="E-mail" className={inputCls} />
              <input required type="password" value={form.senha} onChange={e => set('senha', e.target.value)}
                placeholder="Senha" className={inputCls} />
              <select value={form.role} onChange={e => handleRoleChange(e.target.value as Role)} className={selectCls}>
                <option value="comercial">Comercial</option>
                <option value="contador">Contador</option>
                <option value="gestor">Gestor</option>
                <option value="admin">Admin</option>
              </select>
              <PermissoesSelector
                permissions={form.permissions}
                onChange={p => setForm(f => ({ ...f, permissions: p }))}
              />
              <div className="col-span-1 flex items-center gap-3 sm:col-span-2 lg:col-span-4">
                {erro && <p className="text-xs text-red-600">{erro}</p>}
                <button type="submit" disabled={criando}
                  className="ml-auto rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-50">
                  {criando ? 'Criando…' : '+ Criar Usuário'}
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
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
                  {isAdminOuGestor && <th className="px-4 py-3 text-right">Ações</th>}
                </tr>
              </thead>
              <tbody>
                {items.map(u => (
                  <tr key={u.id} className="border-t border-gray-50 hover:bg-gray-50">
                    <td className="px-4 py-2.5 font-medium text-gray-800">{u.nome}</td>
                    <td className="px-4 py-2.5 text-gray-500">{u.email}</td>
                    <td className="px-4 py-2.5"><Chip label={ROLE_LABEL[u.role]} cor={ROLE_COLOR[u.role]} /></td>
                    <td className="px-4 py-2.5"><AtivoChip ativo={u.ativo} /></td>
                    {isAdminOuGestor && (
                      <td className="px-4 py-2.5 text-right">
                        <span className="inline-flex gap-3">
                          <button onClick={() => setEditandoUsuario(u)}
                            className="text-xs text-blue-500 hover:underline">Editar</button>
                          {podeExcluir && (
                            <BtnExcluir onClick={() => setConfirmExcluir(u)} />
                          )}
                        </span>
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
    </>
  )
}

// ── Seção: Tipos de Lançamento ─────────────────────────────────
function SecaoTipos({ token, podeCriar, podeEditar, podeExcluir }: {
  token: string; podeCriar: boolean; podeEditar: boolean; podeExcluir: boolean
}) {
  const [items, setItems] = useState<TipoItem[]>([])
  const [loading, setLoading] = useState(true)
  const [criando, setCriando] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [confirmExcluir, setConfirmExcluir] = useState<TipoItem | null>(null)
  const [form, setForm] = useState({ nome: '', natureza: 'despesa', categoria: '', custo_tipo: '' })
  const [editForm, setEditForm] = useState({ nome: '', categoria: '', custo_tipo: '' })
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(() => {
    api.get<TipoItem[]>('/configuracoes/tipos', token)
      .then(setItems).catch(() => {}).finally(() => setLoading(false))
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

  async function excluir(t: TipoItem) {
    await api.delete(`/configuracoes/tipos/${t.id}`, token)
    setConfirmExcluir(null); carregar()
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
      {confirmExcluir && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="mb-2 text-sm font-semibold text-gray-800">Excluir tipo?</h3>
            <p className="mb-5 text-sm text-gray-500">
              <strong>{confirmExcluir.nome}</strong> será excluído permanentemente.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmExcluir(null)}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">Cancelar</button>
              <button onClick={() => excluir(confirmExcluir)}
                className="rounded-lg bg-red-600 px-5 py-2 text-sm font-medium text-white hover:bg-red-700">Excluir</button>
            </div>
          </div>
        </div>
      )}

      {podeCriar && (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Novo Tipo</h3>
          <form onSubmit={criar} className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
            <div className="col-span-1 flex items-center gap-3 sm:col-span-2 lg:col-span-4">
              {erro && <p className="text-xs text-red-600">{erro}</p>}
              <button type="submit" disabled={criando}
                className="ml-auto rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-50">
                {criando ? 'Criando…' : '+ Criar Tipo'}
              </button>
            </div>
          </form>
        </div>
      )}

      {[{ label: 'Despesas', cor: 'text-red-600', lista: despesas }, { label: 'Receitas', cor: 'text-green-700', lista: receitas }].map(grupo => (
        <div key={grupo.label} className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <div className="border-b border-gray-100 px-4 py-2.5">
            <h3 className={`text-xs font-semibold uppercase tracking-wide ${grupo.cor}`}>{grupo.label}</h3>
          </div>
          {loading ? <div className="py-6 text-center text-sm text-gray-400">Carregando…</div> : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-medium text-gray-500">
                  <th className="px-4 py-2.5">Nome</th>
                  <th className="px-4 py-2.5">Categoria</th>
                  <th className="px-4 py-2.5">Custo</th>
                  <th className="px-4 py-2.5">Status</th>
                  {(podeEditar || podeExcluir) && <th className="px-4 py-2.5 text-right">Ações</th>}
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
                        {(podeEditar || podeExcluir) && (
                          <td className="px-4 py-2.5 text-right">
                            <span className="inline-flex gap-3">
                              {podeEditar && (
                                <button onClick={() => iniciarEdicao(t)} className="text-xs text-blue-500 hover:underline">Editar</button>
                              )}
                              {podeExcluir && <BtnExcluir onClick={() => setConfirmExcluir(t)} />}
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
function SecaoBancos({ token, podeCriar, podeEditar, podeExcluir }: {
  token: string; podeCriar: boolean; podeEditar: boolean; podeExcluir: boolean
}) {
  const [items, setItems] = useState<BancoItem[]>([])
  const [loading, setLoading] = useState(true)
  const [criando, setCriando] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [confirmExcluir, setConfirmExcluir] = useState<BancoItem | null>(null)
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

  async function excluir(b: BancoItem) {
    await api.delete(`/configuracoes/bancos/${b.id}`, token)
    setConfirmExcluir(null); carregar()
  }

  return (
    <div className="space-y-5">
      {confirmExcluir && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="mb-2 text-sm font-semibold text-gray-800">Excluir banco?</h3>
            <p className="mb-5 text-sm text-gray-500">
              <strong>{confirmExcluir.nome}</strong> será excluído permanentemente.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmExcluir(null)}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">Cancelar</button>
              <button onClick={() => excluir(confirmExcluir)}
                className="rounded-lg bg-red-600 px-5 py-2 text-sm font-medium text-white hover:bg-red-700">Excluir</button>
            </div>
          </div>
        </div>
      )}

      {podeCriar && (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Novo Banco</h3>
          <form onSubmit={criar} className="flex flex-col gap-2 sm:flex-row sm:gap-3">
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

      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
        {loading ? <div className="py-10 text-center text-sm text-gray-400">Carregando…</div> : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">Status</th>
                {(podeEditar || podeExcluir) && <th className="px-4 py-3 text-right">Ações</th>}
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
                      {(podeEditar || podeExcluir) && (
                        <td className="px-4 py-2.5 text-right">
                          <span className="inline-flex gap-3">
                            {podeEditar && (
                              <button onClick={() => { setEditId(b.id); setEditNome(b.nome) }}
                                className="text-xs text-blue-500 hover:underline">Editar</button>
                            )}
                            {podeExcluir && <BtnExcluir onClick={() => setConfirmExcluir(b)} />}
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
function SecaoCentros({ token, podeCriar, podeEditar, podeExcluir }: {
  token: string; podeCriar: boolean; podeEditar: boolean; podeExcluir: boolean
}) {
  const [items, setItems] = useState<CentroItem[]>([])
  const [loading, setLoading] = useState(true)
  const [criando, setCriando] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [confirmExcluir, setConfirmExcluir] = useState<CentroItem | null>(null)
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

  async function excluir(c: CentroItem) {
    await api.delete(`/configuracoes/centros-custo/${c.id}`, token)
    setConfirmExcluir(null); carregar()
  }

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  return (
    <div className="space-y-5">
      {confirmExcluir && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="mb-2 text-sm font-semibold text-gray-800">Excluir centro de custo?</h3>
            <p className="mb-5 text-sm text-gray-500">
              <strong>{confirmExcluir.nome}</strong> será excluído permanentemente.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmExcluir(null)}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">Cancelar</button>
              <button onClick={() => excluir(confirmExcluir)}
                className="rounded-lg bg-red-600 px-5 py-2 text-sm font-medium text-white hover:bg-red-700">Excluir</button>
            </div>
          </div>
        </div>
      )}

      {podeCriar && (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Novo Centro de Custo</h3>
          <form onSubmit={criar} className="flex flex-col gap-2 sm:flex-row sm:gap-3">
            <input required value={form.nome} onChange={e => set('nome', e.target.value)}
              placeholder="Nome" className={`${inputCls} flex-1`} />
            <input required value={form.codigo} onChange={e => set('codigo', e.target.value)}
              placeholder="Código" className={`${inputCls} sm:w-36`} />
            {erro && <p className="self-center text-xs text-red-600">{erro}</p>}
            <button type="submit" disabled={criando}
              className="rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-50 whitespace-nowrap">
              {criando ? 'Criando…' : '+ Criar Centro'}
            </button>
          </form>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
        {loading ? <div className="py-10 text-center text-sm text-gray-400">Carregando…</div> : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                <th className="px-4 py-3">Nome</th>
                <th className="px-4 py-3">Código</th>
                <th className="px-4 py-3">Status</th>
                {(podeEditar || podeExcluir) && <th className="px-4 py-3 text-right">Ações</th>}
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
                      {(podeEditar || podeExcluir) && (
                        <td className="px-4 py-2.5 text-right">
                          <span className="inline-flex gap-3">
                            {podeEditar && (
                              <button onClick={() => { setEditId(c.id); setEditNome(c.nome) }}
                                className="text-xs text-blue-500 hover:underline">Editar</button>
                            )}
                            {podeExcluir && <BtnExcluir onClick={() => setConfirmExcluir(c)} />}
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
export default function ConfiguracoesPage() {
  const { token } = useAuth()
  const { role, permissions } = useUser()

  const isAdminOuGestor = role === 'admin' || role === 'gestor'
  const podeCriar   = permissions?.configuracoes?.criar    ?? false
  const podeEditar  = permissions?.configuracoes?.editar   ?? false
  const podeExcluir = permissions?.configuracoes?.deletar  ?? false

  const ABAS: { id: Aba; label: string; desc: string }[] = [
    { id: 'usuarios', label: 'Usuários',            desc: 'Gerencie os acessos ao sistema' },
    { id: 'tipos',    label: 'Tipos de Lançamento', desc: 'Categorias de despesas e receitas' },
    { id: 'bancos',   label: 'Bancos',              desc: 'Contas bancárias da corretora' },
    { id: 'centros',  label: 'Centros de Custo',    desc: 'Unidades e filiais' },
  ]

  const [aba, setAba] = useState<Aba>('usuarios')

  if (!token || !role) return null

  const abaAtual = ABAS.find(a => a.id === aba) ?? ABAS[0]

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-[#071934] md:text-2xl">Configurações</h1>
        <p className="mt-0.5 text-sm text-gray-500">Gerencie os parâmetros do sistema</p>
      </div>

      {/* Tabs */}
      <div className="grid grid-cols-2 gap-1 rounded-xl border border-gray-200 bg-white p-1 shadow-sm sm:flex">
        {ABAS.map(a => (
          <button key={a.id} onClick={() => setAba(a.id)}
            className={`rounded-lg px-2 py-2.5 text-xs font-medium transition-colors sm:flex-1 sm:px-3 sm:text-sm ${
              aba === a.id ? 'bg-[#071934] text-white shadow-sm' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
            }`}>
            {a.label}
          </button>
        ))}
      </div>

      <p className="text-xs text-gray-400">{abaAtual.desc}</p>

      {aba === 'usuarios' && (
        <SecaoUsuarios token={token} role={role} podeExcluir={podeExcluir} />
      )}
      {aba === 'tipos' && (
        <SecaoTipos token={token} podeCriar={podeCriar} podeEditar={podeEditar} podeExcluir={podeExcluir} />
      )}
      {aba === 'bancos' && (
        <SecaoBancos token={token} podeCriar={podeCriar} podeEditar={podeEditar} podeExcluir={podeExcluir} />
      )}
      {aba === 'centros' && (
        <SecaoCentros token={token} podeCriar={podeCriar} podeEditar={podeEditar} podeExcluir={podeExcluir} />
      )}
    </div>
  )
}
