'use client'
import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'
import { useUser } from '@/contexts/UserContext'
import { api } from '@/lib/api'
import { fmtBRL, mesAnterior } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'

interface TipoLancamento { id: string; nome: string; natureza: string }
interface Banco { id: string; nome: string }

interface Despesa {
  id: string; competencia: string; tipo_lancamento_id: string | null; banco_id: string | null
  tipo_nome: string | null; categoria: string | null; descricao: string
  centro_custo: string; banco_nome: string | null; valor: number; paga_em: string | null; status: string
}
interface DespesasResp { total: number; items: Despesa[]; soma_total: number; total_pendentes: number }

interface Receita {
  id: string; competencia: string; tipo_lancamento_id: string | null; banco_id: string | null
  tipo_nome: string | null; descricao: string; centro_custo: string | null
  banco_nome: string | null; valor: number; recebido_em: string | null
  observacao: string | null; origem: string
}
interface ReceitasResp { total: number; items: Receita[]; soma_total: number }

function fmtCompetencia(d: string) {
  const dt = new Date(d + 'T12:00:00')
  return dt.toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' })
}

function Badge({ text, cor }: { text: string; cor: string }) {
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${cor}`}>{text}</span>
}

function tipoCor(tipo: string | null) {
  const t = (tipo ?? '').toLowerCase()
  if (t.includes('aluguel')) return 'bg-orange-100 text-orange-700'
  if (t.includes('salario') || t.includes('salário')) return 'bg-blue-100 text-blue-700'
  if (t.includes('energia')) return 'bg-yellow-100 text-yellow-700'
  return 'bg-gray-100 text-gray-600'
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pendente:  'bg-amber-50 text-amber-700 border border-amber-200',
    aprovada:  'bg-green-50 text-green-700 border border-green-200',
    rejeitada: 'bg-red-50 text-red-600 border border-red-200',
  }
  const label: Record<string, string> = {
    pendente: 'Pendente',
    aprovada: 'Aprovada',
    rejeitada: 'Rejeitada',
  }
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${map[status] ?? 'bg-gray-100 text-gray-500'}`}>
      {label[status] ?? status}
    </span>
  )
}

// ── Ícones de ação ─────────────────────────────────────────────
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

// ── Campo de formulário reutilizável ───────────────────────────
function Campo({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  )
}

const inputCls = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#071934] focus:outline-none"
const selectCls = inputCls

// ── Modal de Despesa (criar e editar) ──────────────────────────
interface ModalDespesaProps {
  token: string
  tipos: TipoLancamento[]
  bancos: Banco[]
  despesa?: Despesa
  onClose: () => void
  onSaved: () => void
}

function ModalDespesa({ token, tipos, bancos, despesa, onClose, onSaved }: ModalDespesaProps) {
  const editando = !!despesa
  const [form, setForm] = useState({
    tipo_lancamento_id: despesa?.tipo_lancamento_id ?? '',
    banco_id:           despesa?.banco_id ?? '',
    descricao:          despesa?.descricao ?? '',
    valor:              despesa ? String(despesa.valor) : '',
    competencia:        despesa ? despesa.competencia.slice(0, 7) : mesAnterior()[0].slice(0, 7),
    paga_em:            despesa?.paga_em ?? '',
    centro_custo:       despesa?.centro_custo ?? 'matriz',
  })
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    setSalvando(true)
    setErro(null)
    const [y, m] = form.competencia.split('-')
    const payload: Record<string, unknown> = {
      tipo_lancamento_id: form.tipo_lancamento_id || null,
      banco_id:           form.banco_id || null,
      descricao:          form.descricao,
      subcategoria:       form.descricao,
      valor:              parseFloat(form.valor),
      competencia:        `${y}-${m}-01`,
      centro_custo:       form.centro_custo,
    }
    if (form.paga_em) payload.paga_em = form.paga_em
    if (!editando && !form.tipo_lancamento_id) payload.categoria = 'outros'

    try {
      if (editando) {
        await api.patch(`/lancamentos/despesas/${despesa!.id}`, token, payload)
      } else {
        await api.post('/lancamentos/despesas', token, payload)
      }
      onSaved()
      onClose()
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Erro ao salvar')
      setSalvando(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-bold text-[#071934]">{editando ? 'Editar Despesa' : 'Nova Despesa'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {editando && (
          <div className="mb-4 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700">
            A despesa voltará para <strong>Pendente</strong> e precisará de nova aprovação.
          </div>
        )}

        <form onSubmit={salvar} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Campo label="Tipo de lançamento">
              <select value={form.tipo_lancamento_id} onChange={e => set('tipo_lancamento_id', e.target.value)} className={selectCls}>
                <option value="">Selecionar tipo</option>
                {tipos.filter(t => t.natureza === 'despesa').map(t => (
                  <option key={t.id} value={t.id}>{t.nome}</option>
                ))}
              </select>
            </Campo>
            <Campo label="Banco">
              <select value={form.banco_id} onChange={e => set('banco_id', e.target.value)} className={selectCls}>
                <option value="">Sem banco</option>
                {bancos.map(b => <option key={b.id} value={b.id}>{b.nome}</option>)}
              </select>
            </Campo>
          </div>

          <Campo label="Descrição *">
            <input required value={form.descricao} onChange={e => set('descricao', e.target.value)}
              placeholder="Ex: Aluguel sede matriz" className={inputCls} />
          </Campo>

          <div className="grid grid-cols-2 gap-4">
            <Campo label="Valor (R$) *">
              <input required type="number" step="0.01" min="0" value={form.valor}
                onChange={e => set('valor', e.target.value)} placeholder="0,00" className={inputCls} />
            </Campo>
            <Campo label="Competência *">
              <input required type="month" value={form.competencia}
                onChange={e => set('competencia', e.target.value)} className={inputCls} />
            </Campo>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Campo label="Centro de custo">
              <select value={form.centro_custo} onChange={e => set('centro_custo', e.target.value)} className={selectCls}>
                <option value="matriz">Matriz</option>
                <option value="aguas_lindoia">Águas Lindoia</option>
              </select>
            </Campo>
            <Campo label="Pago em">
              <input type="date" value={form.paga_em} onChange={e => set('paga_em', e.target.value)} className={inputCls} />
            </Campo>
          </div>

          {erro && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{erro}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="rounded-lg border border-gray-200 px-5 py-2 text-sm text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={salvando}
              className="rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-60">
              {salvando ? 'Salvando…' : editando ? 'Salvar alterações' : 'Salvar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Modal de Receita (criar e editar) ──────────────────────────
interface ModalReceitaProps {
  token: string
  tipos: TipoLancamento[]
  bancos: Banco[]
  receita?: Receita
  onClose: () => void
  onSaved: () => void
}

function ModalReceita({ token, tipos, bancos, receita, onClose, onSaved }: ModalReceitaProps) {
  const editando = !!receita
  const [form, setForm] = useState({
    tipo_lancamento_id: receita?.tipo_lancamento_id ?? '',
    banco_id:           receita?.banco_id ?? '',
    descricao:          receita?.descricao ?? '',
    valor:              receita ? String(receita.valor) : '',
    competencia:        receita ? receita.competencia.slice(0, 7) : mesAnterior()[0].slice(0, 7),
    recebido_em:        receita?.recebido_em ?? '',
    centro_custo:       receita?.centro_custo ?? 'matriz',
    observacao:         receita?.observacao ?? '',
  })
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    setSalvando(true)
    setErro(null)
    const [y, m] = form.competencia.split('-')
    const payload: Record<string, unknown> = {
      tipo_lancamento_id: form.tipo_lancamento_id || null,
      banco_id:           form.banco_id || null,
      descricao:          form.descricao,
      valor:              parseFloat(form.valor),
      competencia:        `${y}-${m}-01`,
      centro_custo:       form.centro_custo,
    }
    if (form.recebido_em) payload.recebido_em = form.recebido_em
    if (form.observacao)  payload.observacao  = form.observacao

    try {
      if (editando) {
        await api.patch(`/lancamentos/receitas/${receita!.id}`, token, payload)
      } else {
        await api.post('/lancamentos/receitas', token, payload)
      }
      onSaved()
      onClose()
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Erro ao salvar')
      setSalvando(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-bold text-[#071934]">{editando ? 'Editar Receita' : 'Nova Receita'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <form onSubmit={salvar} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Campo label="Tipo de lançamento">
              <select value={form.tipo_lancamento_id} onChange={e => set('tipo_lancamento_id', e.target.value)} className={selectCls}>
                <option value="">Selecionar tipo</option>
                {tipos.filter(t => t.natureza === 'receita').map(t => (
                  <option key={t.id} value={t.id}>{t.nome}</option>
                ))}
              </select>
            </Campo>
            <Campo label="Banco">
              <select value={form.banco_id} onChange={e => set('banco_id', e.target.value)} className={selectCls}>
                <option value="">Sem banco</option>
                {bancos.map(b => <option key={b.id} value={b.id}>{b.nome}</option>)}
              </select>
            </Campo>
          </div>

          <Campo label="Descrição *">
            <input required value={form.descricao} onChange={e => set('descricao', e.target.value)}
              placeholder="Ex: Comissão extra" className={inputCls} />
          </Campo>

          <div className="grid grid-cols-2 gap-4">
            <Campo label="Valor (R$) *">
              <input required type="number" step="0.01" min="0" value={form.valor}
                onChange={e => set('valor', e.target.value)} placeholder="0,00" className={inputCls} />
            </Campo>
            <Campo label="Competência *">
              <input required type="month" value={form.competencia}
                onChange={e => set('competencia', e.target.value)} className={inputCls} />
            </Campo>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Campo label="Centro de custo">
              <select value={form.centro_custo} onChange={e => set('centro_custo', e.target.value)} className={selectCls}>
                <option value="matriz">Matriz</option>
                <option value="aguas_lindoia">Águas Lindoia</option>
              </select>
            </Campo>
            <Campo label="Recebido em">
              <input type="date" value={form.recebido_em} onChange={e => set('recebido_em', e.target.value)} className={inputCls} />
            </Campo>
          </div>

          <Campo label="Observação">
            <input value={form.observacao} onChange={e => set('observacao', e.target.value)}
              placeholder="Opcional" className={inputCls} />
          </Campo>

          {erro && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{erro}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="rounded-lg border border-gray-200 px-5 py-2 text-sm text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={salvando}
              className="rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-60">
              {salvando ? 'Salvando…' : editando ? 'Salvar alterações' : 'Salvar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Página principal ───────────────────────────────────────────
export default function LancamentosPage() {
  const { token } = useAuth()
  const { role } = useUser()
  const podeAprovar = role === 'admin' || role === 'gestor'
  const [mes, setMes] = useState(mesAnterior()[0].slice(0, 7))
  const [aba, setAba] = useState<'despesas' | 'receitas'>('despesas')
  const [despesas, setDespesas] = useState<DespesasResp | null>(null)
  const [receitas, setReceitas] = useState<ReceitasResp | null>(null)
  const [tipos, setTipos]   = useState<TipoLancamento[]>([])
  const [bancos, setBancos] = useState<Banco[]>([])
  const [loadingDespesas, setLoadingDespesas] = useState(true)
  const [loadingReceitas, setLoadingReceitas] = useState(true)
  const [modalDespesa, setModalDespesa] = useState(false)
  const [modalReceita, setModalReceita] = useState(false)
  const [editandoDespesa, setEditandoDespesa] = useState<Despesa | null>(null)
  const [editandoReceita, setEditandoReceita]  = useState<Receita | null>(null)
  const [confirmandoId, setConfirmandoId] = useState<string | null>(null)
  const [deletando, setDeletando] = useState(false)
  const [erroDelete, setErroDelete] = useState<string | null>(null)

  function mesParaDatas(m: string): [string, string] {
    const [y, mo] = m.split('-')
    const last = new Date(Number(y), Number(mo), 0).getDate()
    return [`${y}-${mo}-01`, `${y}-${mo}-${last}`]
  }

  const buscarDespesas = useCallback(() => {
    if (!token) return
    const [inicio, fim] = mesParaDatas(mes)
    setLoadingDespesas(true)
    api.get<DespesasResp>(`/lancamentos/despesas?inicio=${inicio}&fim=${fim}`, token)
      .then(setDespesas)
      .catch(() => {})
      .finally(() => setLoadingDespesas(false))
  }, [token, mes])

  const buscarReceitas = useCallback(() => {
    if (!token) return
    const [inicio, fim] = mesParaDatas(mes)
    setLoadingReceitas(true)
    api.get<ReceitasResp>(`/lancamentos/receitas?inicio=${inicio}&fim=${fim}`, token)
      .then(setReceitas)
      .catch(() => {})
      .finally(() => setLoadingReceitas(false))
  }, [token, mes])

  useEffect(() => { buscarDespesas() }, [buscarDespesas])
  useEffect(() => { buscarReceitas() }, [buscarReceitas])

  useEffect(() => {
    if (!token) return
    Promise.all([
      api.get<TipoLancamento[]>('/configuracoes/tipos', token),
      api.get<Banco[]>('/configuracoes/bancos', token),
    ]).then(([t, b]) => { setTipos(t); setBancos(b) }).catch(() => {})
  }, [token])

  const totalDespesas = despesas?.soma_total ?? 0
  const totalReceitas = receitas?.soma_total ?? 0
  const saldo = totalReceitas - totalDespesas

  async function deletarDespesa(id: string) {
    if (!token) return
    setDeletando(true)
    setErroDelete(null)
    try {
      await api.delete(`/lancamentos/despesas/${id}`, token)
      setDespesas(prev => {
        if (!prev) return prev
        const items = prev.items.filter(d => d.id !== id)
        const soma_total = items.reduce((acc, d) => acc + Number(d.valor), 0)
        return { ...prev, items, total: items.length, soma_total }
      })
      setConfirmandoId(null)
    } catch (e) {
      setErroDelete(e instanceof Error ? e.message : 'Erro ao excluir despesa.')
      setConfirmandoId(null)
    } finally {
      setDeletando(false)
    }
  }

  async function deletarReceita(id: string) {
    if (!token) return
    setDeletando(true)
    setErroDelete(null)
    try {
      await api.delete(`/lancamentos/receitas/${id}`, token)
      setReceitas(prev => {
        if (!prev) return prev
        const items = prev.items.filter(r => r.id !== id)
        const soma_total = items.reduce((acc, r) => acc + Number(r.valor), 0)
        return { ...prev, items, total: items.length, soma_total }
      })
      setConfirmandoId(null)
    } catch (e) {
      setErroDelete(e instanceof Error ? e.message : 'Erro ao excluir receita.')
      setConfirmandoId(null)
    } finally {
      setDeletando(false)
    }
  }

  return (
    <>
      {(modalDespesa || editandoDespesa) && token && (
        <ModalDespesa
          token={token} tipos={tipos} bancos={bancos}
          despesa={editandoDespesa ?? undefined}
          onClose={() => { setModalDespesa(false); setEditandoDespesa(null) }}
          onSaved={buscarDespesas}
        />
      )}
      {(modalReceita || editandoReceita) && token && (
        <ModalReceita
          token={token} tipos={tipos} bancos={bancos}
          receita={editandoReceita ?? undefined}
          onClose={() => { setModalReceita(false); setEditandoReceita(null) }}
          onSaved={buscarReceitas}
        />
      )}

      <div className="space-y-6">
        {/* Cabeçalho */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-[#071934]">Lançamentos</h1>
            <p className="mt-0.5 text-sm text-gray-500">Despesas e receitas por centro de custo e banco</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span>De</span>
              <input type="month" value={mes} onChange={(e) => setMes(e.target.value)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm focus:outline-none" />
              <span>Até</span>
              <input type="month" value={mes} onChange={(e) => setMes(e.target.value)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm focus:outline-none" />
            </div>
            <button
              onClick={() => aba === 'despesas' ? setModalDespesa(true) : setModalReceita(true)}
              className="flex items-center gap-1 rounded-lg bg-[#071934] px-4 py-2 text-sm font-medium text-white hover:bg-[#0E2444]">
              + {aba === 'despesas' ? 'Nova Despesa' : 'Nova Receita'}
            </button>
          </div>
        </div>

        {/* Cards resumo */}
        <div className="grid grid-cols-3 gap-4">
          <div className="flex items-center gap-3 rounded-2xl bg-white p-4 shadow-sm">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-red-50">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-red-500">
                <polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/>
              </svg>
            </div>
            <div>
              <p className="text-xs text-gray-500">Total Despesas</p>
              {loadingDespesas
                ? <div className="mt-1 h-5 w-24 animate-pulse rounded bg-gray-100" />
                : <p className="text-base font-bold text-red-500">{fmtBRL(totalDespesas)}</p>}
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-2xl bg-white p-4 shadow-sm">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-green-50">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-green-500">
                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
              </svg>
            </div>
            <div>
              <p className="text-xs text-gray-500">Total Receitas</p>
              {loadingReceitas
                ? <div className="mt-1 h-5 w-24 animate-pulse rounded bg-gray-100" />
                : <p className="text-base font-bold text-green-600">{fmtBRL(totalReceitas)}</p>}
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-2xl bg-white p-4 shadow-sm">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-blue-600">
                <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
              </svg>
            </div>
            <div>
              <p className="text-xs text-gray-500">Saldo do Período</p>
              {loadingDespesas || loadingReceitas
                ? <div className="mt-1 h-5 w-24 animate-pulse rounded bg-gray-100" />
                : <p className={`text-base font-bold ${saldo >= 0 ? 'text-green-600' : 'text-red-500'}`}>{fmtBRL(saldo)}</p>}
            </div>
          </div>
        </div>

        {/* Banner de pendentes — visível apenas para quem pode aprovar */}
        {podeAprovar && (despesas?.total_pendentes ?? 0) > 0 && (
          <div className="flex items-center justify-between rounded-xl bg-amber-50 border border-amber-200 px-4 py-3">
            <div className="flex items-center gap-2 text-sm text-amber-800">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4 shrink-0">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span><strong>{despesas!.total_pendentes}</strong> despesa{despesas!.total_pendentes > 1 ? 's' : ''} aguardando aprovação</span>
            </div>
            <Link href="/dashboard/lancamentos/aprovacoes"
              className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700">
              Ver Kanban →
            </Link>
          </div>
        )}

        {/* Erro de exclusão */}
        {erroDelete && (
          <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600 flex items-center justify-between">
            <span>{erroDelete}</span>
            <button onClick={() => setErroDelete(null)} className="ml-4 text-red-400 hover:text-red-600">✕</button>
          </div>
        )}

        {/* Tabela */}
        <div className="rounded-2xl bg-white shadow-sm overflow-hidden">
          <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
            <div className="flex gap-1">
              <button onClick={() => setAba('despesas')}
                className={`rounded-lg px-4 py-1.5 text-sm font-medium ${aba === 'despesas' ? 'bg-red-50 text-red-600' : 'text-gray-500 hover:bg-gray-50'}`}>
                Despesas {despesas ? `(${despesas.total})` : ''}
              </button>
              <button onClick={() => setAba('receitas')}
                className={`rounded-lg px-4 py-1.5 text-sm font-medium ${aba === 'receitas' ? 'bg-green-50 text-green-600' : 'text-gray-500 hover:bg-gray-50'}`}>
                Receitas {receitas ? `(${receitas.total})` : ''}
              </button>
            </div>
            <div className="flex gap-2">
              <select className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 focus:outline-none">
                <option>Todos os bancos</option>
                {bancos.map(b => <option key={b.id}>{b.nome}</option>)}
              </select>
              <select className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-600 focus:outline-none">
                <option>Todos os centros</option>
                <option value="matriz">Matriz</option>
                <option value="aguas_lindoia">Águas Lindoia</option>
              </select>
            </div>
          </div>

          {(aba === 'despesas' ? loadingDespesas : loadingReceitas) ? (
            <div className="p-5"><Skeleton variant="table" /></div>
          ) : aba === 'despesas' ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                  <th className="px-5 py-3">Competência</th>
                  <th className="px-5 py-3">Tipo</th>
                  <th className="px-5 py-3">Descrição</th>
                  <th className="px-5 py-3">Centro</th>
                  <th className="px-5 py-3">Banco</th>
                  <th className="px-5 py-3 text-right">Valor</th>
                  <th className="px-5 py-3">Pago em</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-3 py-3" />
                </tr>
              </thead>
              <tbody>
                {(despesas?.items ?? []).map((d) => (
                  <tr key={d.id} className="border-t border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-600">{fmtCompetencia(d.competencia)}</td>
                    <td className="px-5 py-3">
                      <Badge text={d.tipo_nome ?? d.categoria ?? '—'} cor={tipoCor(d.tipo_nome ?? d.categoria)} />
                    </td>
                    <td className="px-5 py-3 text-gray-700">{d.descricao}</td>
                    <td className="px-5 py-3 capitalize text-gray-600">{d.centro_custo.replace('_', ' ')}</td>
                    <td className="px-5 py-3 text-gray-600">{d.banco_nome ?? '—'}</td>
                    <td className="px-5 py-3 text-right font-medium tabular-nums text-red-500">{fmtBRL(d.valor)}</td>
                    <td className="px-5 py-3 text-gray-400">{d.paga_em ?? '—'}</td>
                    <td className="px-5 py-3"><StatusBadge status={d.status} /></td>
                    <td className="px-3 py-3 text-right">
                      {confirmandoId === d.id ? (
                        <span className="inline-flex items-center gap-2">
                          <button onClick={() => deletarDespesa(d.id)} disabled={deletando}
                            className="text-xs font-medium text-red-500 hover:text-red-700 disabled:opacity-50">
                            {deletando ? 'Excluindo…' : 'Confirmar'}
                          </button>
                          <span className="text-gray-300">|</span>
                          <button onClick={() => setConfirmandoId(null)}
                            className="text-xs text-gray-400 hover:text-gray-600">
                            Cancelar
                          </button>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-2">
                          <button onClick={() => setEditandoDespesa(d)}
                            className="text-gray-300 hover:text-blue-500 transition-colors" title="Editar">
                            <IconLapis />
                          </button>
                          <button onClick={() => setConfirmandoId(d.id)}
                            className="text-gray-300 hover:text-red-400 transition-colors" title="Excluir">
                            <IconLixo />
                          </button>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
                {(despesas?.items ?? []).length === 0 && (
                  <tr><td colSpan={9} className="py-10 text-center text-sm text-gray-400">Nenhuma despesa no período</td></tr>
                )}
              </tbody>
              {(despesas?.soma_total ?? 0) > 0 && (
                <tfoot>
                  <tr className="border-t-2 border-gray-100">
                    <td colSpan={5} className="px-5 py-3 font-semibold text-gray-700">Total</td>
                    <td className="px-5 py-3 text-right font-bold tabular-nums text-red-500">{fmtBRL(despesas!.soma_total)}</td>
                    <td colSpan={3} />
                  </tr>
                </tfoot>
              )}
            </table>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                  <th className="px-5 py-3">Competência</th>
                  <th className="px-5 py-3">Tipo</th>
                  <th className="px-5 py-3">Descrição</th>
                  <th className="px-5 py-3">Centro</th>
                  <th className="px-5 py-3">Banco</th>
                  <th className="px-5 py-3 text-right">Valor</th>
                  <th className="px-5 py-3">Recebido em</th>
                  <th className="px-3 py-3" />
                </tr>
              </thead>
              <tbody>
                {(receitas?.items ?? []).map((r) => (
                  <tr key={r.id} className="border-t border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-600">{fmtCompetencia(r.competencia)}</td>
                    <td className="px-5 py-3"><Badge text={r.tipo_nome ?? '—'} cor="bg-green-100 text-green-700" /></td>
                    <td className="px-5 py-3 text-gray-700">{r.descricao}</td>
                    <td className="px-5 py-3 capitalize text-gray-600">{r.centro_custo?.replace('_',' ') ?? '—'}</td>
                    <td className="px-5 py-3 text-gray-600">{r.banco_nome ?? '—'}</td>
                    <td className="px-5 py-3 text-right font-medium tabular-nums text-green-600">{fmtBRL(r.valor)}</td>
                    <td className="px-5 py-3 text-gray-400">{r.recebido_em ?? '—'}</td>
                    <td className="px-3 py-3 text-right">
                      {confirmandoId === r.id ? (
                        <span className="inline-flex items-center gap-2">
                          <button onClick={() => deletarReceita(r.id)} disabled={deletando}
                            className="text-xs font-medium text-red-500 hover:text-red-700 disabled:opacity-50">
                            {deletando ? 'Excluindo…' : 'Confirmar'}
                          </button>
                          <span className="text-gray-300">|</span>
                          <button onClick={() => setConfirmandoId(null)}
                            className="text-xs text-gray-400 hover:text-gray-600">
                            Cancelar
                          </button>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-2">
                          {r.origem === 'manual' && (
                            <button onClick={() => setEditandoReceita(r)}
                              className="text-gray-300 hover:text-blue-500 transition-colors" title="Editar">
                              <IconLapis />
                            </button>
                          )}
                          <button onClick={() => setConfirmandoId(r.id)}
                            className="text-gray-300 hover:text-red-400 transition-colors" title="Excluir">
                            <IconLixo />
                          </button>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
                {(receitas?.items ?? []).length === 0 && (
                  <tr><td colSpan={8} className="py-10 text-center text-sm text-gray-400">Nenhuma receita no período</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  )
}


