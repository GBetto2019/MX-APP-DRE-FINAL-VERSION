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
  recorrente: boolean; parcela_atual: number | null; parcela_total: number | null
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
    competencia:        despesa ? despesa.competencia.slice(0, 7) : mesAnterior()[0].slice(0, 7),
    paga_em:            despesa?.paga_em ?? '',
    centro_custo:       despesa?.centro_custo ?? 'matriz',
    recorrente:         despesa?.recorrente ?? false,
    // Parcelamento
    valor_total:        despesa ? String(despesa.valor * (despesa.parcela_total ?? 1)) : '',
    num_parcelas:       String(despesa?.parcela_total ?? 1),
  })
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const set = (k: string, v: string | boolean) => setForm(f => ({ ...f, [k]: v }))

  const numParcelas = Math.max(1, parseInt(form.num_parcelas) || 1)
  const valorTotal  = parseFloat(form.valor_total) || 0
  const valorMensal = numParcelas > 1 && valorTotal > 0 ? valorTotal / numParcelas : valorTotal
  const parcelado   = numParcelas > 1

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    if (valorMensal <= 0) { setErro('Informe um valor válido.'); return }
    setSalvando(true)
    setErro(null)
    const [y, m] = form.competencia.split('-')

    try {
      if (editando) {
        const payload: Record<string, unknown> = {
          tipo_lancamento_id: form.tipo_lancamento_id || null,
          banco_id:           form.banco_id || null,
          descricao:          form.descricao,
          subcategoria:       form.descricao,
          valor:              valorMensal,
          competencia:        `${y}-${m}-01`,
          centro_custo:       form.centro_custo,
        }
        if (form.paga_em) payload.paga_em = form.paga_em
        await api.patch(`/lancamentos/despesas/${despesa!.id}`, token, payload)
      } else if (parcelado) {
        // Cria N parcelas, uma por mês
        for (let i = 0; i < numParcelas; i++) {
          const d = new Date(Number(y), Number(m) - 1 + i, 1)
          const cy = d.getFullYear()
          const cm = String(d.getMonth() + 1).padStart(2, '0')
          const payload: Record<string, unknown> = {
            tipo_lancamento_id: form.tipo_lancamento_id || null,
            banco_id:           form.banco_id || null,
            descricao:          form.descricao,
            subcategoria:       form.descricao,
            valor:              valorMensal,
            competencia:        `${cy}-${cm}-01`,
            centro_custo:       form.centro_custo,
            recorrente:         false,
            parcela_atual:      i + 1,
            parcela_total:      numParcelas,
          }
          if (!form.tipo_lancamento_id) payload.categoria = 'outros'
          await api.post('/lancamentos/despesas', token, payload)
        }
      } else {
        const payload: Record<string, unknown> = {
          tipo_lancamento_id: form.tipo_lancamento_id || null,
          banco_id:           form.banco_id || null,
          descricao:          form.descricao,
          subcategoria:       form.descricao,
          valor:              valorMensal,
          competencia:        `${y}-${m}-01`,
          centro_custo:       form.centro_custo,
          recorrente:         form.recorrente,
        }
        if (form.paga_em) payload.paga_em = form.paga_em
        if (!form.tipo_lancamento_id) payload.categoria = 'outros'
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
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4">
      <div className="max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-4 shadow-xl sm:max-w-lg sm:rounded-2xl sm:p-6">
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
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
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

          {/* Valor e Parcelamento */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
            <Campo label={parcelado ? 'Valor Total (R$) *' : 'Valor (R$) *'}>
              <input required type="number" step="0.01" min="0.01" value={form.valor_total}
                onChange={e => set('valor_total', e.target.value)} placeholder="0,00" className={inputCls} />
            </Campo>
            <Campo label="Nº de Parcelas">
              <input type="number" min="1" max="60" value={form.num_parcelas}
                onChange={e => set('num_parcelas', e.target.value)} className={inputCls}
                disabled={editando} />
            </Campo>
          </div>

          {parcelado && valorTotal > 0 && (
            <div className="rounded-lg bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
              Valor mensal calculado: <strong>R$ {valorMensal.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</strong> × {numParcelas} parcelas
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
            <Campo label="Competência (1ª parcela) *">
              <input required type="month" value={form.competencia}
                onChange={e => set('competencia', e.target.value)} className={inputCls} />
            </Campo>
            <Campo label="Centro de custo">
              <select value={form.centro_custo} onChange={e => set('centro_custo', e.target.value)} className={selectCls}>
                <option value="matriz">Matriz</option>
                <option value="aguas_lindoia">Águas Lindoia</option>
              </select>
            </Campo>
          </div>

          {!parcelado && !editando && (
            <Campo label="Pago em">
              <input type="date" value={form.paga_em} onChange={e => set('paga_em', e.target.value)} className={inputCls} />
            </Campo>
          )}

          {/* Recorrente — só aparece quando não é parcelado e não está editando */}
          {!parcelado && !editando && (
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.recorrente as boolean}
                onChange={e => set('recorrente', e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-[#071934] focus:ring-[#071934]"
              />
              <span className="text-sm text-gray-700">Despesa recorrente (repete todo mês)</span>
            </label>
          )}

          {erro && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{erro}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="rounded-lg border border-gray-200 px-5 py-2 text-sm text-gray-600 hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={salvando}
              className="rounded-lg bg-[#071934] px-5 py-2 text-sm font-medium text-white hover:bg-[#0E2444] disabled:opacity-60">
              {salvando ? 'Salvando…' : editando ? 'Salvar alterações' : parcelado ? `Criar ${numParcelas} parcelas` : 'Salvar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Tipos de receita com valor único mensal
const TIPOS_VALOR_UNICO = ['comissões de vendas', 'comissões - adicionais / premiações', 'receitas de vendas']

// ── Modal de Receita (criar e editar) ──────────────────────────
interface ModalReceitaProps {
  token: string
  tipos: TipoLancamento[]
  bancos: Banco[]
  receita?: Receita
  receitasCarregadas?: Receita[]
  onClose: () => void
  onSaved: () => void
}

function ModalReceita({ token, tipos, receita, receitasCarregadas, onClose, onSaved }: Omit<ModalReceitaProps, 'bancos'>) {
  const editando = !!receita
  const [form, setForm] = useState({
    tipo_lancamento_id: receita?.tipo_lancamento_id ?? '',
    descricao:          receita?.descricao ?? '',
    valor:              receita ? String(receita.valor) : '',
    competencia:        receita ? receita.competencia.slice(0, 7) : mesAnterior()[0].slice(0, 7),
    recebido_em:        receita?.recebido_em ?? '',
    centro_custo:       receita?.centro_custo ?? 'matriz',
    observacao:         receita?.observacao ?? '',
    recorrente:         false,
    data_final:         '',
  })
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const set = (k: string, v: string | boolean) => setForm(f => ({ ...f, [k]: v }))

  // Detecta se o tipo selecionado é de valor único mensal
  const tipoSelecionado = tipos.find(t => t.id === form.tipo_lancamento_id)
  const isTipoUnico = tipoSelecionado
    ? TIPOS_VALOR_UNICO.some(n => tipoSelecionado.nome.toLowerCase().includes(n))
    : false

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    setSalvando(true)
    setErro(null)
    const [y, m] = form.competencia.split('-')
    const compMes = `${y}-${m}-01`

    // Verificação frontend de duplicata para tipos únicos mensais
    if (!editando && isTipoUnico && Array.isArray(receitasCarregadas)) {
      const existe = (receitasCarregadas as Receita[]).some((r: Receita) =>
        r.tipo_lancamento_id === form.tipo_lancamento_id &&
        r.competencia.slice(0, 7) === form.competencia
      )
      if (existe) {
        setErro(`Já existe um lançamento de "${tipoSelecionado?.nome}" para este mês. Edite o registro existente.`)
        setSalvando(false)
        return
      }
    }

    const basePayload: Record<string, unknown> = {
      tipo_lancamento_id: form.tipo_lancamento_id || null,
      descricao:          form.descricao,
      valor:              parseFloat(form.valor),
      centro_custo:       form.centro_custo,
    }
    if (form.recebido_em) basePayload.recebido_em = form.recebido_em
    if (form.observacao)  basePayload.observacao  = form.observacao

    try {
      if (editando) {
        await api.patch(`/lancamentos/receitas/${receita!.id}`, token, { ...basePayload, competencia: `${form.competencia.split('-')[0]}-${form.competencia.split('-')[1]}-01` })
      } else if (form.recorrente && form.data_final && form.data_final >= form.competencia) {
        // Cria um registro por mês do período
        const [sy, sm] = form.competencia.split('-').map(Number)
        const [ey, em] = form.data_final.split('-').map(Number)
        const meses = (ey - sy) * 12 + (em - sm) + 1
        for (let i = 0; i < meses; i++) {
          const d = new Date(sy, sm - 1 + i, 1)
          const cy = d.getFullYear()
          const cm = String(d.getMonth() + 1).padStart(2, '0')
          await api.post('/lancamentos/receitas', token, { ...basePayload, competencia: `${cy}-${cm}-01` })
        }
      } else {
        await api.post('/lancamentos/receitas', token, { ...basePayload, competencia: `${form.competencia.split('-')[0]}-${form.competencia.split('-')[1]}-01` })
      }
      onSaved()
      onClose()
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Erro ao salvar')
      setSalvando(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4">
      <div className="max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white p-4 shadow-xl sm:max-w-lg sm:rounded-2xl sm:p-6">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-bold text-[#071934]">{editando ? 'Editar Receita' : 'Nova Receita'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <form onSubmit={salvar} className="space-y-4">
          <Campo label="Tipo de lançamento">
            <select value={form.tipo_lancamento_id} onChange={e => set('tipo_lancamento_id', e.target.value)} className={selectCls}>
              <option value="">Selecionar tipo</option>
              {tipos.filter(t => t.natureza === 'receita').map(t => (
                <option key={t.id} value={t.id}>{t.nome}</option>
              ))}
            </select>
          </Campo>

          {isTipoUnico && (
            <div className="rounded-lg bg-blue-50 border border-blue-100 px-3 py-2 text-xs text-blue-700">
              Este tipo permite apenas <strong>1 lançamento por mês</strong>. Duplicatas são bloqueadas automaticamente.
            </div>
          )}

          <Campo label="Descrição *">
            <input required value={form.descricao} onChange={e => set('descricao', e.target.value)}
              placeholder="Ex: Comissão extra" className={inputCls} />
          </Campo>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
            <Campo label="Valor (R$) *">
              <input required type="number" step="0.01" min="0" value={form.valor}
                onChange={e => set('valor', e.target.value)} placeholder="0,00" className={inputCls} />
            </Campo>
            <Campo label="Competência *">
              <input required type="month" value={form.competencia}
                onChange={e => set('competencia', e.target.value)} className={inputCls} />
            </Campo>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
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

          {/* Receita Recorrente */}
          {!editando && (
            <div className="space-y-3 rounded-xl border border-gray-100 bg-gray-50 p-3">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.recorrente as boolean}
                  onChange={e => set('recorrente', e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-[#071934] focus:ring-[#071934]"
                />
                <span className="text-sm font-medium text-gray-700">Receita Recorrente</span>
              </label>
              {form.recorrente && (
                <Campo label="Repetir até (mês/ano) *">
                  <input
                    required={form.recorrente as boolean}
                    type="month"
                    value={form.data_final}
                    min={form.competencia}
                    onChange={e => set('data_final', e.target.value)}
                    className={inputCls}
                  />
                </Campo>
              )}
              {form.recorrente && form.data_final && form.data_final >= form.competencia && (() => {
                const [sy, sm] = form.competencia.split('-').map(Number)
                const [ey, em] = form.data_final.split('-').map(Number)
                const n = (ey - sy) * 12 + (em - sm) + 1
                return n > 1 ? (
                  <p className="text-xs text-blue-600">Serão criados <strong>{n} registros</strong> mensais.</p>
                ) : null
              })()}
            </div>
          )}

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
  // Dialog para exclusão de parcelas futuras
  const [dialogParcelas, setDialogParcelas] = useState<{ id: string; total: number } | null>(null)

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

  async function deletarDespesa(id: string, excluirFuturas = false) {
    if (!token) return
    setDeletando(true)
    setErroDelete(null)
    try {
      const params = excluirFuturas ? { excluir_futuras: 'true' } : undefined
      await api.delete(`/lancamentos/despesas/${id}`, token, params)
      setDespesas(prev => {
        if (!prev) return prev
        // Se excluiu futuras, remove da lista todas as parcelas com parcela_atual >= atual
        const despesaExcluida = prev.items.find(d => d.id === id)
        const items = excluirFuturas && despesaExcluida?.parcela_total
          ? prev.items.filter(d =>
              d.id !== id &&
              !(
                d.tipo_lancamento_id === despesaExcluida.tipo_lancamento_id &&
                d.descricao === despesaExcluida.descricao &&
                d.parcela_total === despesaExcluida.parcela_total &&
                (despesaExcluida.parcela_atual == null || (d.parcela_atual ?? 0) > (despesaExcluida.parcela_atual ?? 0))
              )
            )
          : prev.items.filter(d => d.id !== id)
        const soma_total = items.reduce((acc, d) => acc + Number(d.valor), 0)
        return { ...prev, items, total: items.length, soma_total }
      })
      setConfirmandoId(null)
      setDialogParcelas(null)
    } catch (e) {
      setErroDelete(e instanceof Error ? e.message : 'Erro ao excluir despesa.')
      setConfirmandoId(null)
      setDialogParcelas(null)
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
          token={token} tipos={tipos}
          receita={editandoReceita ?? undefined}
          receitasCarregadas={receitas?.items}
          onClose={() => { setModalReceita(false); setEditandoReceita(null) }}
          onSaved={buscarReceitas}
        />
      )}

      {/* Dialog: excluir parcelas futuras */}
      {dialogParcelas && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-[#071934]">Excluir parcela</h3>
            <p className="mt-2 text-sm text-gray-600">
              Esta despesa faz parte de um grupo de <strong>{dialogParcelas.total} parcelas</strong>.
              Deseja excluir também as parcelas futuras?
            </p>
            <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end">
              <button
                onClick={() => { setDialogParcelas(null); setConfirmandoId(null) }}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
                Cancelar
              </button>
              <button
                onClick={() => deletarDespesa(dialogParcelas.id, false)}
                disabled={deletando}
                className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50">
                Só esta parcela
              </button>
              <button
                onClick={() => deletarDespesa(dialogParcelas.id, true)}
                disabled={deletando}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
                {deletando ? 'Excluindo…' : 'Esta e as futuras'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-6">
        {/* Cabeçalho */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-[#071934] md:text-2xl">Lançamentos</h1>
            <p className="mt-0.5 text-sm text-gray-500">Despesas e receitas por centro de custo e banco</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span className="shrink-0">De</span>
              <input type="month" value={mes} onChange={(e) => setMes(e.target.value)}
                className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none" />
              <span className="shrink-0">Até</span>
              <input type="month" value={mes} onChange={(e) => setMes(e.target.value)}
                className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none" />
            </div>
            <div className="flex w-full gap-2 sm:w-auto">
              <button
                onClick={() => { setAba('despesas'); setModalDespesa(true) }}
                className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-[#071934] px-3 py-2.5 text-sm font-medium text-[#071934] hover:bg-[#071934] hover:text-white transition-colors sm:flex-none">
                + Despesa
              </button>
              <button
                onClick={() => { setAba('receitas'); setModalReceita(true) }}
                className="flex flex-1 items-center justify-center gap-1 rounded-lg bg-[#071934] px-3 py-2.5 text-sm font-medium text-white hover:bg-[#0E2444] sm:flex-none">
                + Nova Receita
              </button>
            </div>
          </div>
        </div>

        {/* Cards resumo */}
        <div className="grid grid-cols-3 gap-2 sm:gap-4">
          <div className="rounded-2xl bg-white p-3 shadow-sm sm:p-4">
            <div className="flex items-center gap-2">
              <div className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-red-50 sm:flex">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-red-500">
                  <polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/>
                </svg>
              </div>
              <p className="text-[10px] font-medium text-gray-500 sm:text-xs">Total Despesas</p>
            </div>
            {loadingDespesas
              ? <div className="mt-1.5 h-4 w-full animate-pulse rounded bg-gray-100 sm:h-5" />
              : <p className="mt-1 text-xs font-bold tabular-nums text-red-500 sm:text-base">{fmtBRL(totalDespesas)}</p>}
          </div>
          <div className="rounded-2xl bg-white p-3 shadow-sm sm:p-4">
            <div className="flex items-center gap-2">
              <div className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-green-50 sm:flex">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-green-500">
                  <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
                </svg>
              </div>
              <p className="text-[10px] font-medium text-gray-500 sm:text-xs">Total Receitas</p>
            </div>
            {loadingReceitas
              ? <div className="mt-1.5 h-4 w-full animate-pulse rounded bg-gray-100 sm:h-5" />
              : <p className="mt-1 text-xs font-bold tabular-nums text-green-600 sm:text-base">{fmtBRL(totalReceitas)}</p>}
          </div>
          <div className="rounded-2xl bg-white p-3 shadow-sm sm:p-4">
            <div className="flex items-center gap-2">
              <div className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 sm:flex">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-blue-600">
                  <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                </svg>
              </div>
              <p className="text-[10px] font-medium text-gray-500 sm:text-xs">Saldo do Período</p>
            </div>
            {loadingDespesas || loadingReceitas
              ? <div className="mt-1.5 h-4 w-full animate-pulse rounded bg-gray-100 sm:h-5" />
              : <p className={`mt-1 text-xs font-bold tabular-nums sm:text-base ${saldo >= 0 ? 'text-green-600' : 'text-red-500'}`}>{fmtBRL(saldo)}</p>}
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
          <div className="flex flex-col gap-2 border-b border-gray-100 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <div className="flex gap-1">
              <button onClick={() => setAba('despesas')}
                className={`rounded-lg px-3 py-2 text-sm font-medium sm:px-4 ${aba === 'despesas' ? 'bg-red-50 text-red-600' : 'text-gray-500 hover:bg-gray-50'}`}>
                Despesas {despesas ? `(${despesas.total})` : ''}
              </button>
              <button onClick={() => setAba('receitas')}
                className={`rounded-lg px-3 py-2 text-sm font-medium sm:px-4 ${aba === 'receitas' ? 'bg-green-50 text-green-600' : 'text-gray-500 hover:bg-gray-50'}`}>
                Receitas {receitas ? `(${receitas.total})` : ''}
              </button>
            </div>
            <div className="flex gap-2">
              <select className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 focus:outline-none sm:flex-none sm:py-1.5">
                <option>Todos os bancos</option>
                {bancos.map(b => <option key={b.id}>{b.nome}</option>)}
              </select>
              <select className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 focus:outline-none sm:flex-none sm:py-1.5">
                <option>Todos os centros</option>
                <option value="matriz">Matriz</option>
                <option value="aguas_lindoia">Águas Lindoia</option>
              </select>
            </div>
          </div>

          {(aba === 'despesas' ? loadingDespesas : loadingReceitas) ? (
            <div className="p-5"><Skeleton variant="table" /></div>
          ) : aba === 'despesas' ? (
            <>
              {/* Mobile: card list */}
              <div className="divide-y divide-gray-50 sm:hidden">
                {(despesas?.items ?? []).length === 0 ? (
                  <p className="py-10 text-center text-sm text-gray-400">Nenhuma despesa no período</p>
                ) : (despesas?.items ?? []).map((d) => (
                  <div key={d.id} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-gray-800">
                          {d.descricao}
                          {d.parcela_total && d.parcela_total > 1 && (
                            <span className="ml-1 rounded-full bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600">{d.parcela_atual}/{d.parcela_total}</span>
                          )}
                          {d.recorrente && !d.parcela_total && (
                            <span className="ml-1 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600">recorrente</span>
                          )}
                        </p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          <Badge text={d.tipo_nome ?? d.categoria ?? '—'} cor={tipoCor(d.tipo_nome ?? d.categoria)} />
                          <StatusBadge status={d.status} />
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="text-xs font-bold tabular-nums text-red-500">{fmtBRL(d.valor)}</p>
                        <p className="mt-0.5 text-[10px] text-gray-400">{fmtCompetencia(d.competencia)}</p>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <p className="text-xs text-gray-400 capitalize">
                        {d.centro_custo.replace('_', ' ')}
                        {d.banco_nome ? ` · ${d.banco_nome}` : ''}
                        {d.paga_em ? ` · Pago ${d.paga_em}` : ''}
                      </p>
                      {confirmandoId === d.id ? (
                        <span className="inline-flex items-center gap-2">
                          <button onClick={() => deletarDespesa(d.id)} disabled={deletando}
                            className="text-xs font-medium text-red-500 hover:text-red-700 disabled:opacity-50">
                            {deletando ? 'Excluindo…' : 'Confirmar'}
                          </button>
                          <span className="text-gray-300">|</span>
                          <button onClick={() => setConfirmandoId(null)} className="text-xs text-gray-400 hover:text-gray-600">Cancelar</button>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-2">
                          <button onClick={() => setEditandoDespesa(d)} className="text-gray-300 hover:text-blue-500 transition-colors" title="Editar"><IconLapis /></button>
                          <button onClick={() => d.parcela_total && d.parcela_total > 1 ? setDialogParcelas({ id: d.id, total: d.parcela_total }) : setConfirmandoId(d.id)} className="text-gray-300 hover:text-red-400 transition-colors" title="Excluir"><IconLixo /></button>
                        </span>
                      )}
                    </div>
                  </div>
                ))}
                {(despesas?.soma_total ?? 0) > 0 && (
                  <div className="flex items-center justify-between px-4 py-3">
                    <span className="text-sm font-semibold text-gray-700">Total</span>
                    <span className="text-sm font-bold tabular-nums text-red-500">{fmtBRL(despesas!.soma_total)}</span>
                  </div>
                )}
              </div>
              {/* Desktop: table */}
              <div className="hidden overflow-x-auto sm:block">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-100 text-left text-[11px] font-medium text-gray-500">
                      <th className="px-4 py-2">Competência</th>
                      <th className="px-4 py-2">Tipo</th>
                      <th className="px-4 py-2">Descrição</th>
                      <th className="px-4 py-2">Centro</th>
                      <th className="px-4 py-2">Banco</th>
                      <th className="px-4 py-2 text-right">Valor</th>
                      <th className="px-4 py-2">Pago em</th>
                      <th className="px-4 py-2">Status</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {(despesas?.items ?? []).map((d) => (
                      <tr key={d.id} className="border-t border-gray-50 hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-600">{fmtCompetencia(d.competencia)}</td>
                        <td className="px-4 py-2"><Badge text={d.tipo_nome ?? d.categoria ?? '—'} cor={tipoCor(d.tipo_nome ?? d.categoria)} /></td>
                        <td className="px-4 py-2 text-gray-700">
                          <span>{d.descricao}</span>
                          {d.parcela_total && d.parcela_total > 1 && (
                            <span className="ml-1.5 rounded-full bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600">
                              {d.parcela_atual}/{d.parcela_total}
                            </span>
                          )}
                          {d.recorrente && !d.parcela_total && (
                            <span className="ml-1.5 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-600">recorrente</span>
                          )}
                        </td>
                        <td className="px-4 py-2 capitalize text-gray-600">{d.centro_custo.replace('_', ' ')}</td>
                        <td className="px-4 py-2 text-gray-600">{d.banco_nome ?? '—'}</td>
                        <td className="px-4 py-2 text-right font-medium tabular-nums text-red-500">{fmtBRL(d.valor)}</td>
                        <td className="px-4 py-2 text-gray-400">{d.paga_em ?? '—'}</td>
                        <td className="px-4 py-2"><StatusBadge status={d.status} /></td>
                        <td className="px-3 py-2 text-right">
                          {confirmandoId === d.id ? (
                            <span className="inline-flex items-center gap-2">
                              <button onClick={() => deletarDespesa(d.id)} disabled={deletando}
                                className="text-xs font-medium text-red-500 hover:text-red-700 disabled:opacity-50">
                                {deletando ? 'Excluindo…' : 'Confirmar'}
                              </button>
                              <span className="text-gray-300">|</span>
                              <button onClick={() => setConfirmandoId(null)} className="text-xs text-gray-400 hover:text-gray-600">Cancelar</button>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-2">
                              <button onClick={() => setEditandoDespesa(d)} className="text-gray-300 hover:text-blue-500 transition-colors" title="Editar"><IconLapis /></button>
                              <button onClick={() => d.parcela_total && d.parcela_total > 1 ? setDialogParcelas({ id: d.id, total: d.parcela_total }) : setConfirmandoId(d.id)} className="text-gray-300 hover:text-red-400 transition-colors" title="Excluir"><IconLixo /></button>
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {(despesas?.items ?? []).length === 0 && (
                      <tr><td colSpan={9} className="py-10 text-center text-xs text-gray-400">Nenhuma despesa no período</td></tr>
                    )}
                  </tbody>
                  {(despesas?.soma_total ?? 0) > 0 && (
                    <tfoot>
                      <tr className="border-t-2 border-gray-100">
                        <td colSpan={5} className="px-4 py-2 font-semibold text-gray-700">Total</td>
                        <td className="px-4 py-2 text-right font-bold tabular-nums text-red-500">{fmtBRL(despesas!.soma_total)}</td>
                        <td colSpan={3} />
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </>
          ) : (
            <>
              {/* Mobile: card list */}
              <div className="divide-y divide-gray-50 sm:hidden">
                {(receitas?.items ?? []).length === 0 ? (
                  <p className="py-10 text-center text-sm text-gray-400">Nenhuma receita no período</p>
                ) : (receitas?.items ?? []).map((r) => (
                  <div key={r.id} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-gray-800">{r.descricao}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          <Badge text={r.tipo_nome ?? '—'} cor="bg-green-100 text-green-700" />
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="text-xs font-bold tabular-nums text-green-600">{fmtBRL(r.valor)}</p>
                        <p className="mt-0.5 text-[10px] text-gray-400">{fmtCompetencia(r.competencia)}</p>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <p className="text-xs text-gray-400 capitalize">
                        {r.centro_custo?.replace('_', ' ') ?? ''}
                        {r.banco_nome ? ` · ${r.banco_nome}` : ''}
                        {r.recebido_em ? ` · Recebido ${r.recebido_em}` : ''}
                      </p>
                      {confirmandoId === r.id ? (
                        <span className="inline-flex items-center gap-2">
                          <button onClick={() => deletarReceita(r.id)} disabled={deletando}
                            className="text-xs font-medium text-red-500 hover:text-red-700 disabled:opacity-50">
                            {deletando ? 'Excluindo…' : 'Confirmar'}
                          </button>
                          <span className="text-gray-300">|</span>
                          <button onClick={() => setConfirmandoId(null)} className="text-xs text-gray-400 hover:text-gray-600">Cancelar</button>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-2">
                          {r.origem === 'manual' && (
                            <button onClick={() => setEditandoReceita(r)} className="text-gray-300 hover:text-blue-500 transition-colors" title="Editar"><IconLapis /></button>
                          )}
                          <button onClick={() => setConfirmandoId(r.id)} className="text-gray-300 hover:text-red-400 transition-colors" title="Excluir"><IconLixo /></button>
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {/* Desktop: table */}
              <div className="hidden overflow-x-auto sm:block">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-100 text-left text-[11px] font-medium text-gray-500">
                      <th className="px-4 py-2">Competência</th>
                      <th className="px-4 py-2">Tipo</th>
                      <th className="px-4 py-2">Descrição</th>
                      <th className="px-4 py-2">Centro</th>
                      <th className="px-4 py-2">Banco</th>
                      <th className="px-4 py-2 text-right">Valor</th>
                      <th className="px-4 py-2">Recebido em</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {(receitas?.items ?? []).map((r) => (
                      <tr key={r.id} className="border-t border-gray-50 hover:bg-gray-50">
                        <td className="px-4 py-2 text-gray-600">{fmtCompetencia(r.competencia)}</td>
                        <td className="px-4 py-2"><Badge text={r.tipo_nome ?? '—'} cor="bg-green-100 text-green-700" /></td>
                        <td className="px-4 py-2 text-gray-700">{r.descricao}</td>
                        <td className="px-4 py-2 capitalize text-gray-600">{r.centro_custo?.replace('_',' ') ?? '—'}</td>
                        <td className="px-4 py-2 text-gray-600">{r.banco_nome ?? '—'}</td>
                        <td className="px-4 py-2 text-right font-medium tabular-nums text-green-600">{fmtBRL(r.valor)}</td>
                        <td className="px-4 py-2 text-gray-400">{r.recebido_em ?? '—'}</td>
                        <td className="px-3 py-2 text-right">
                          {confirmandoId === r.id ? (
                            <span className="inline-flex items-center gap-2">
                              <button onClick={() => deletarReceita(r.id)} disabled={deletando}
                                className="text-xs font-medium text-red-500 hover:text-red-700 disabled:opacity-50">
                                {deletando ? 'Excluindo…' : 'Confirmar'}
                              </button>
                              <span className="text-gray-300">|</span>
                              <button onClick={() => setConfirmandoId(null)} className="text-xs text-gray-400 hover:text-gray-600">Cancelar</button>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-2">
                              {r.origem === 'manual' && (
                                <button onClick={() => setEditandoReceita(r)} className="text-gray-300 hover:text-blue-500 transition-colors" title="Editar"><IconLapis /></button>
                              )}
                              <button onClick={() => setConfirmandoId(r.id)} className="text-gray-300 hover:text-red-400 transition-colors" title="Excluir"><IconLixo /></button>
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {(receitas?.items ?? []).length === 0 && (
                      <tr><td colSpan={8} className="py-10 text-center text-xs text-gray-400">Nenhuma receita no período</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}


