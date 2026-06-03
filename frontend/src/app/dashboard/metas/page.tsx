'use client'
import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useUser } from '@/contexts/UserContext'
import { api } from '@/lib/api'
import { fmtBRL, fmtPct } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'
import type { MetaItem, MetasResponse, MetaCadastroItem, UsuarioItem } from '@/types'

// ── Constantes ─────────────────────────────────────────────────

const METRICAS = [
  { value: 'receita_bruta',      label: 'Receita Bruta' },
  { value: 'comissao_liquida',   label: 'Comissão Líquida' },
  { value: 'numero_apolices',    label: 'Nº Apólices' },
]

const METRICA_LABEL: Record<string, string> = {
  receita_bruta:    'Receita Bruta',
  comissao_liquida: 'Comissão Líquida',
  numero_apolices:  'Nº Apólices',
}

const ROLE_LABEL: Record<string, string> = {
  admin: 'Admin', gestor: 'Gestor', contador: 'Contador', comercial: 'Comercial',
}

// ── Helpers ────────────────────────────────────────────────────

function fmtValorMeta(valor: number, metrica: string) {
  return metrica === 'numero_apolices' ? `${Math.round(valor)} apól.` : fmtBRL(valor)
}

function fmtComp(comp: string) {
  const meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
  const [y, m] = comp.split('-')
  return `${meses[parseInt(m) - 1]}/${y.slice(2)}`
}

function getStatus(meta: MetaCadastroItem, atingimento?: MetaItem) {
  const hoje = new Date()
  const [y, m] = meta.competencia.split('-').map(Number)
  const isPast = y < hoje.getFullYear() || (y === hoje.getFullYear() && m < hoje.getMonth() + 1)

  if (!atingimento) {
    return isPast
      ? { label: 'Encerrada', cor: 'bg-gray-100 text-gray-500' }
      : { label: 'Vigente',   cor: 'bg-blue-50 text-blue-600' }
  }
  if (atingimento.atingida) return { label: 'Atingida',       cor: 'bg-green-50 text-green-700' }
  if (isPast)                return { label: 'Não atingida',   cor: 'bg-red-50 text-red-600' }
  return                            { label: 'Em andamento',   cor: 'bg-amber-50 text-amber-700' }
}

// ── Ícones ─────────────────────────────────────────────────────

const IconLapis = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
)
const IconLixo = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/>
    <path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
  </svg>
)
const IconClose = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
)

// ── Componente de formulário ────────────────────────────────────

function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  )
}
const inputCls  = 'w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#071934] focus:outline-none'
const selectCls = inputCls

// ── Modal de criar / editar meta ────────────────────────────────

interface ModalMetaProps {
  token: string
  usuarios: UsuarioItem[]
  meta?: MetaCadastroItem
  mes: string
  usuarioPreSel?: string
  onClose: () => void
  onSaved: () => void
}

function ModalMeta({ token, usuarios, meta, mes, usuarioPreSel, onClose, onSaved }: ModalMetaProps) {
  const editando = !!meta
  const [form, setForm] = useState({
    escopo:      meta?.escopo ?? 'produtor',
    escopo_id:   meta?.escopo_id ?? usuarioPreSel ?? '',
    metrica:     meta?.metrica ?? 'receita_bruta',
    competencia: meta ? meta.competencia.slice(0, 7) : mes,
    valor_alvo:  meta ? String(meta.valor_alvo) : '',
  })
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    setSalvando(true); setErro(null)
    try {
      if (editando) {
        await api.put(`/metas/${meta!.id}`, token, {
          metrica:    form.metrica,
          valor_alvo: parseFloat(form.valor_alvo),
        })
      } else {
        const [y, m] = form.competencia.split('-')
        await api.post('/metas', token, {
          escopo:      form.escopo,
          escopo_id:   form.escopo === 'global' ? null : (form.escopo_id || null),
          competencia: `${y}-${m}-01`,
          metrica:     form.metrica,
          valor_alvo:  parseFloat(form.valor_alvo),
        })
      }
      onSaved(); onClose()
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Erro ao salvar')
      setSalvando(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4">
      <div className="max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-4 shadow-xl sm:max-w-md sm:rounded-2xl sm:p-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-bold text-[#071934]">{editando ? 'Editar Meta' : 'Nova Meta'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><IconClose /></button>
        </div>

        <form onSubmit={salvar} className="space-y-4">
          {!editando && (
            <>
              <Campo label="Escopo">
                <select value={form.escopo} onChange={e => set('escopo', e.target.value)} className={selectCls}>
                  <option value="produtor">Por usuário</option>
                  <option value="global">Global (todos)</option>
                </select>
              </Campo>
              {form.escopo === 'produtor' && (
                <Campo label="Usuário *">
                  <select required value={form.escopo_id} onChange={e => set('escopo_id', e.target.value)} className={selectCls}>
                    <option value="">Selecionar usuário</option>
                    {usuarios.map(u => (
                      <option key={u.id} value={u.id}>
                        {u.nome} — {ROLE_LABEL[u.role] ?? u.role}
                      </option>
                    ))}
                  </select>
                </Campo>
              )}
              <Campo label="Competência (prazo) *">
                <input
                  required type="month" value={form.competencia}
                  onChange={e => set('competencia', e.target.value)}
                  className={inputCls}
                />
              </Campo>
            </>
          )}

          <Campo label="Métrica *">
            <select required value={form.metrica} onChange={e => set('metrica', e.target.value)} className={selectCls}>
              {METRICAS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </Campo>

          <Campo label={`Valor Alvo${form.metrica === 'numero_apolices' ? ' (apólices)' : ' (R$)'} *`}>
            <input
              required type="number" step={form.metrica === 'numero_apolices' ? '1' : '0.01'}
              min="0.01" value={form.valor_alvo}
              onChange={e => set('valor_alvo', e.target.value)}
              placeholder={form.metrica === 'numero_apolices' ? '100' : '0,00'}
              className={inputCls}
            />
          </Campo>

          {erro && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{erro}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="rounded-lg border border-gray-200 px-5 py-2 text-sm text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={salvando}
              className="rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-60">
              {salvando ? 'Salvando…' : editando ? 'Salvar alterações' : 'Criar Meta'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Página principal ────────────────────────────────────────────

export default function MetasPage() {
  const { token }  = useAuth()
  const { role }   = useUser()
  const isAdmin    = role === 'admin'

  const hoje = new Date()
  const [mes, setMes] = useState(
    `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}`
  )

  // Dados
  const [progresso, setProgresso]   = useState<MetasResponse | null>(null)
  const [cadastro,  setCadastro]    = useState<MetaCadastroItem[]>([])
  const [usuarios,  setUsuarios]    = useState<UsuarioItem[]>([])
  const [loading,   setLoading]     = useState(true)
  const [erro,      setErro]        = useState<string | null>(null)

  // Estado modal
  const [modalAberto,     setModalAberto]     = useState(false)
  const [editandoMeta,    setEditandoMeta]    = useState<MetaCadastroItem | null>(null)
  const [usuarioPreSel,   setUsuarioPreSel]   = useState<string | undefined>()
  const [confirmandoId,   setConfirmandoId]   = useState<string | null>(null)
  const [deletando,       setDeletando]       = useState(false)
  const [erroDel,         setErroDel]         = useState<string | null>(null)

  const buscar = useCallback(() => {
    if (!token) return
    setLoading(true); setErro(null)
    const competencia = `${mes}-01`

    const calls: Promise<unknown>[] = [
      api.get<MetasResponse>(`/metas?competencia=${competencia}`, token),
    ]
    if (isAdmin) {
      calls.push(
        api.get<MetaCadastroItem[]>(`/metas/cadastro?competencia=${competencia}`, token),
        api.get<{ total: number; items: UsuarioItem[] }>('/usuarios', token),
      )
    }

    Promise.all(calls)
      .then(([prog, cad, usr]) => {
        setProgresso(prog as MetasResponse)
        if (isAdmin) {
          setCadastro((cad as MetaCadastroItem[]) ?? [])
          setUsuarios(((usr as { items: UsuarioItem[] })?.items ?? []).filter(u => u.ativo))
        }
      })
      .catch(e => setErro(e.message))
      .finally(() => setLoading(false))
  }, [token, mes, isAdmin])

  useEffect(() => { buscar() }, [buscar])

  async function handleDeletar(metaId: string) {
    if (!token) return
    setDeletando(true); setErroDel(null)
    try {
      await api.delete(`/metas/${metaId}`, token)
      setCadastro(prev => prev.filter(m => m.id !== metaId))
      setConfirmandoId(null)
      buscar()
    } catch (e) {
      setErroDel(e instanceof Error ? e.message : 'Erro ao excluir meta.')
      setConfirmandoId(null)
    } finally {
      setDeletando(false)
    }
  }

  function abrirNovaMeta(usuarioId?: string) {
    setEditandoMeta(null)
    setUsuarioPreSel(usuarioId)
    setModalAberto(true)
  }

  function abrirEdicao(meta: MetaCadastroItem) {
    setEditandoMeta(meta)
    setUsuarioPreSel(undefined)
    setModalAberto(true)
  }

  // Mapa meta_id → atingimento
  const atingMap = Object.fromEntries(
    (progresso?.items ?? []).map(m => [m.meta_id, m])
  )

  // ── Controles de período (header) ─────────────────────────────

  const headerControles = (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <h1 className="text-xl font-bold text-[#071934] md:text-2xl">Metas</h1>
      <div className="flex items-center gap-2">
        <input
          type="month" value={mes} onChange={e => setMes(e.target.value)}
          className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none sm:flex-none sm:py-1.5"
        />
        <button onClick={buscar}
          className="rounded-lg bg-[#071934] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#0E2444] sm:py-2">
          Consultar
        </button>
        {isAdmin && (
          <button onClick={() => abrirNovaMeta()}
            className="flex items-center gap-1 rounded-lg bg-[#B5A882] px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 sm:py-2">
            + Nova Meta
          </button>
        )}
      </div>
    </div>
  )

  // ── Loading ────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="space-y-6">
        {headerControles}
        <Skeleton variant="table" className="h-48" />
        {isAdmin && <Skeleton variant="table" className="h-48" />}
      </div>
    )
  }

  // ── Erro global ────────────────────────────────────────────────

  if (erro) {
    return (
      <div className="space-y-6">
        {headerControles}
        <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">{erro}</div>
      </div>
    )
  }

  // ══════════════════════════════════════════════════════════════
  // VISÃO DO ADMIN — gestão de metas por usuário
  // ══════════════════════════════════════════════════════════════

  if (isAdmin) {
    // Metas globais (sem escopo_id)
    const metasGlobais = cadastro.filter(m => m.escopo === 'global')

    // Metas por usuário: map userId → MetaCadastroItem[]
    const metasPorUsuario: Record<string, MetaCadastroItem[]> = {}
    cadastro.filter(m => m.escopo_id).forEach(m => {
      if (!metasPorUsuario[m.escopo_id!]) metasPorUsuario[m.escopo_id!] = []
      metasPorUsuario[m.escopo_id!].push(m)
    })

    const renderMetaRow = (meta: MetaCadastroItem) => {
      const ating  = atingMap[meta.id]
      const status = getStatus(meta, ating)
      const conf   = confirmandoId === meta.id

      return (
        <div key={meta.id} className="border-t border-gray-50 px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-gray-800">
                  {METRICA_LABEL[meta.metrica] ?? meta.metrica}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${status.cor}`}>
                  {status.label}
                </span>
                {ating?.atingida && (
                  <span className="text-xs text-green-600 font-medium">✓</span>
                )}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-0.5 text-xs text-gray-500">
                <span>Prazo: <strong className="text-gray-700">{fmtComp(meta.competencia)}</strong></span>
                <span>Meta: <strong className="text-gray-700">{fmtValorMeta(meta.valor_alvo, meta.metrica)}</strong></span>
                {ating && (
                  <span>
                    Atual: <strong className="text-[#071934]">{fmtValorMeta(Number(ating.valor_atual), meta.metrica)}</strong>
                    <span className="ml-1 text-gray-400">({fmtPct(ating.percentual)})</span>
                  </span>
                )}
              </div>
              {ating && (
                <div className="mt-2 h-1.5 w-full rounded-full bg-gray-100">
                  <div
                    className={`h-1.5 rounded-full ${ating.atingida ? 'bg-green-500' : 'bg-[#071934]'}`}
                    style={{ width: `${Math.min(Number(ating.percentual), 100)}%` }}
                  />
                </div>
              )}
            </div>

            <div className="shrink-0 flex items-center gap-1.5 pt-0.5">
              {conf ? (
                <span className="flex items-center gap-2 text-xs">
                  <button
                    onClick={() => handleDeletar(meta.id)} disabled={deletando}
                    className="font-medium text-red-500 hover:text-red-700 disabled:opacity-50">
                    {deletando ? '…' : 'Confirmar'}
                  </button>
                  <span className="text-gray-200">|</span>
                  <button onClick={() => setConfirmandoId(null)} className="text-gray-400 hover:text-gray-600">
                    Cancelar
                  </button>
                </span>
              ) : (
                <>
                  <button
                    onClick={() => abrirEdicao(meta)}
                    className="text-gray-300 hover:text-blue-500 transition-colors" title="Editar">
                    <IconLapis />
                  </button>
                  <button
                    onClick={() => setConfirmandoId(meta.id)}
                    className="text-gray-300 hover:text-red-400 transition-colors" title="Excluir">
                    <IconLixo />
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )
    }

    return (
      <>
        {(modalAberto || editandoMeta) && token && (
          <ModalMeta
            token={token}
            usuarios={usuarios}
            meta={editandoMeta ?? undefined}
            mes={mes}
            usuarioPreSel={usuarioPreSel}
            onClose={() => { setModalAberto(false); setEditandoMeta(null) }}
            onSaved={buscar}
          />
        )}

        <div className="space-y-5">
          {headerControles}

          {erroDel && (
            <div className="flex items-center justify-between rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">
              <span>{erroDel}</span>
              <button onClick={() => setErroDel(null)} className="ml-3 text-red-400 hover:text-red-600">✕</button>
            </div>
          )}

          {/* Metas globais */}
          {metasGlobais.length > 0 && (
            <div className="overflow-hidden rounded-2xl bg-white shadow-sm">
              <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
                <div>
                  <p className="text-sm font-semibold text-[#071934]">Global</p>
                  <p className="text-xs text-gray-400">Aplicada a todos os perfis</p>
                </div>
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                  {metasGlobais.length} meta{metasGlobais.length !== 1 ? 's' : ''}
                </span>
              </div>
              {metasGlobais.map(renderMetaRow)}
            </div>
          )}

          {/* Um card por usuário */}
          {usuarios.map(u => {
            const metas = metasPorUsuario[u.id] ?? []
            return (
              <div key={u.id} className="overflow-hidden rounded-2xl bg-white shadow-sm">
                <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
                  <div>
                    <p className="text-sm font-semibold text-[#071934]">{u.nome}</p>
                    <p className="text-xs text-gray-400 capitalize">{ROLE_LABEL[u.role] ?? u.role}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {metas.length > 0 && (
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                        {metas.length} meta{metas.length !== 1 ? 's' : ''}
                      </span>
                    )}
                    <button
                      onClick={() => abrirNovaMeta(u.id)}
                      className="rounded-lg border border-[#071934] px-2.5 py-1 text-xs font-medium text-[#071934] hover:bg-[#071934] hover:text-white transition-colors">
                      + Meta
                    </button>
                  </div>
                </div>

                {metas.length === 0 ? (
                  <div className="px-4 py-4 text-center text-xs text-gray-400">
                    Nenhuma meta definida para {fmtComp(`${mes}-01`)}
                  </div>
                ) : (
                  metas.map(renderMetaRow)
                )}
              </div>
            )
          })}

          {usuarios.length === 0 && metasGlobais.length === 0 && (
            <div className="rounded-2xl bg-white px-4 py-10 text-center text-sm text-gray-400 shadow-sm">
              Nenhuma meta cadastrada para {fmtComp(`${mes}-01`)}. Clique em <strong>+ Nova Meta</strong> para começar.
            </div>
          )}
        </div>
      </>
    )
  }

  // ══════════════════════════════════════════════════════════════
  // VISÃO NÃO-ADMIN — barras de progresso (comportamento original)
  // ══════════════════════════════════════════════════════════════

  return (
    <div className="space-y-6">
      {headerControles}

      <div className="rounded-2xl bg-white p-5 shadow-sm space-y-5">
        {(progresso?.items ?? []).length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-400">
            Nenhuma meta cadastrada para {fmtComp(`${mes}-01`)}
          </p>
        ) : (
          (progresso?.items ?? []).map((meta) => (
            <div key={meta.meta_id}>
              <div className="flex items-center justify-between mb-1.5">
                <div>
                  <span className="text-sm font-medium text-gray-700">
                    {METRICA_LABEL[meta.metrica] ?? meta.metrica.replace(/_/g, ' ')}
                  </span>
                  <span className="ml-2 text-xs text-gray-400 capitalize">({meta.escopo})</span>
                </div>
                <div className="text-right">
                  <span className={`text-sm font-semibold ${meta.atingida ? 'text-green-600' : 'text-[#071934]'}`}>
                    {fmtPct(meta.percentual)}
                  </span>
                  <span className="ml-2 text-xs text-gray-400">
                    {fmtValorMeta(Number(meta.valor_atual), meta.metrica)} / {fmtValorMeta(meta.valor_alvo, meta.metrica)}
                  </span>
                </div>
              </div>
              <div className="h-2 w-full rounded-full bg-gray-100">
                <div
                  className={`h-2 rounded-full transition-all ${meta.atingida ? 'bg-green-500' : 'bg-[#071934]'}`}
                  style={{ width: `${Math.min(Number(meta.percentual), 100)}%` }}
                />
              </div>
              {meta.atingida && (
                <p className="mt-1 text-xs text-green-600 font-medium">✓ Meta atingida</p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
