'use client'
import { useEffect, useState, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { fmtBRL } from '@/lib/utils'
import type { Despesa, DespesasResponse } from '@/types'

function mesAtual() {
  const d = new Date()
  d.setMonth(d.getMonth() - 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function fmtCompetencia(d: string) {
  return new Date(d + 'T12:00:00').toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' })
}

// ── Card de despesa no Kanban ──────────────────────────────────
interface CardProps {
  despesa: Despesa
  processandoId: string | null
  onAprovar?: (id: string) => void
  onIniciarRejeicao?: (id: string) => void
  onDragStart?: (id: string) => void
}

function DespesaCard({ despesa, processandoId, onAprovar, onIniciarRejeicao, onDragStart }: CardProps) {
  const ocupado = processandoId === despesa.id
  const arrastavel = despesa.status === 'pendente' && !ocupado

  return (
    <div
      draggable={arrastavel}
      onDragStart={arrastavel && onDragStart ? (e) => { e.dataTransfer.effectAllowed = 'move'; onDragStart(despesa.id) } : undefined}
      className={`rounded-xl border bg-white p-4 shadow-sm transition-opacity select-none
        ${ocupado ? 'opacity-60' : ''}
        ${arrastavel ? 'cursor-grab active:cursor-grabbing active:shadow-lg active:scale-[1.02] transition-transform' : ''}
      `}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="inline-flex rounded-full px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 truncate max-w-[65%]">
          {despesa.tipo_nome ?? despesa.categoria ?? 'Outro'}
        </span>
        <span className="text-xs font-bold text-red-500 tabular-nums whitespace-nowrap">
          {fmtBRL(despesa.valor)}
        </span>
      </div>

      <p className="mt-2 text-xs font-medium text-gray-800 line-clamp-2 leading-snug">
        {despesa.descricao}
      </p>

      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-400">
        <span className="capitalize">{despesa.centro_custo.replace('_', ' ')}</span>
        <span>·</span>
        <span>{fmtCompetencia(despesa.competencia)}</span>
      </div>

      {/* Motivo de rejeição */}
      {despesa.status === 'rejeitada' && despesa.rejeitado_motivo && (
        <div className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
          <span className="font-semibold">Motivo: </span>
          {despesa.rejeitado_motivo}
        </div>
      )}

      {/* Ações para pendentes */}
      {onAprovar && onIniciarRejeicao && despesa.status === 'pendente' && (
        <div className="mt-3 flex gap-2 border-t border-gray-100 pt-3">
          <button
            onClick={() => onAprovar(despesa.id)}
            disabled={ocupado}
            className="flex-1 flex items-center justify-center gap-1 rounded-lg bg-green-500 px-2 py-1.5 text-xs font-semibold text-white hover:bg-green-600 disabled:opacity-50 transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="h-3.5 w-3.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            Aprovar
          </button>
          <button
            onClick={() => onIniciarRejeicao(despesa.id)}
            disabled={ocupado}
            className="flex-1 flex items-center justify-center gap-1 rounded-lg border border-red-200 px-2 py-1.5 text-xs font-semibold text-red-500 hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="h-3.5 w-3.5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
            Rejeitar
          </button>
        </div>
      )}
    </div>
  )
}

// ── Coluna do Kanban ───────────────────────────────────────────
interface ColunaProps {
  titulo: string
  contagem: number
  cor: string
  corTexto: string
  aceitaDrop?: boolean
  onDrop?: () => void
  children: React.ReactNode
}

function KanbanColuna({ titulo, contagem, cor, corTexto, aceitaDrop, onDrop, children }: ColunaProps) {
  const [dragOver, setDragOver] = useState(false)

  return (
    <div className="flex w-[calc(100vw-2rem)] shrink-0 snap-start flex-col sm:w-auto sm:min-w-0">
      <div className={`mb-3 flex items-center justify-between rounded-xl px-4 py-2.5 ${cor}`}>
        <h3 className={`text-sm font-semibold ${corTexto}`}>{titulo}</h3>
        <span className={`rounded-full bg-white/25 px-2.5 py-0.5 text-xs font-bold ${corTexto}`}>
          {contagem}
        </span>
      </div>
      <div
        onDragOver={aceitaDrop ? (e) => { e.preventDefault(); setDragOver(true) } : undefined}
        onDragLeave={aceitaDrop ? () => setDragOver(false) : undefined}
        onDrop={aceitaDrop && onDrop ? (e) => { e.preventDefault(); setDragOver(false); onDrop() } : undefined}
        className={`flex-1 space-y-3 overflow-y-auto rounded-xl pr-1 transition-colors
          ${dragOver ? 'bg-white/60 ring-2 ring-inset ring-white/50' : ''}
        `}
        style={{ maxHeight: 'calc(100vh - 260px)' }}
      >
        {children}
      </div>
    </div>
  )
}

// ── Modal de rejeição ──────────────────────────────────────────
function ModalRejeicao({
  onConfirmar,
  onCancelar,
  loading,
}: {
  onConfirmar: (motivo: string) => void
  onCancelar: () => void
  loading: boolean
}) {
  const [motivo, setMotivo] = useState('')

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4">
      <div className="w-full rounded-t-2xl bg-white p-4 shadow-xl sm:max-w-md sm:rounded-2xl sm:p-6">
        <h3 className="text-base font-bold text-[#071934]">Rejeitar Despesa</h3>
        <p className="mt-1 text-sm text-gray-500">Informe o motivo da rejeição. O lançador será notificado.</p>

        <textarea
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          placeholder="Ex: Nota fiscal ausente, valor divergente, centro de custo incorreto…"
          className="mt-4 w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm text-gray-700 placeholder-gray-400 focus:border-red-300 focus:outline-none focus:ring-1 focus:ring-red-200 resize-none"
          rows={4}
          autoFocus
        />

        {!motivo.trim() && (
          <p className="mt-1 text-xs text-red-400">A justificativa é obrigatória.</p>
        )}

        <div className="mt-4 flex justify-end gap-3">
          <button
            onClick={onCancelar}
            className="rounded-lg border border-gray-200 px-5 py-2 text-sm text-gray-600 hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            onClick={() => onConfirmar(motivo)}
            disabled={!motivo.trim() || loading}
            className="rounded-lg bg-red-500 px-5 py-2 text-sm font-semibold text-white hover:bg-red-600 disabled:opacity-50"
          >
            {loading ? 'Rejeitando…' : 'Confirmar Rejeição'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Página principal ───────────────────────────────────────────
export default function AprovacoesPage() {
  const { token } = useAuth()
  const [despesas, setDespesas] = useState<Despesa[]>([])
  const [loading, setLoading] = useState(true)
  const [processandoId, setProcessandoId] = useState<string | null>(null)
  const [rejeitandoId, setRejeitandoId] = useState<string | null>(null)
  const [erroGlobal, setErroGlobal] = useState<string | null>(null)
  const [mes, setMes] = useState(mesAtual)
  const dragId = useRef<string | null>(null)

  function mesParaDatas(m: string): [string, string] {
    const [y, mo] = m.split('-')
    const last = new Date(Number(y), Number(mo), 0).getDate()
    return [`${y}-${mo}-01`, `${y}-${mo}-${last}`]
  }

  const buscar = useCallback(() => {
    if (!token) return
    const [inicio, fim] = mesParaDatas(mes)
    setLoading(true)
    api.get<DespesasResponse>(`/lancamentos/despesas?inicio=${inicio}&fim=${fim}`, token)
      .then(r => setDespesas(r.items))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [token, mes])

  useEffect(() => { buscar() }, [buscar])

  async function handleAprovar(id: string) {
    if (!token) return
    setProcessandoId(id)
    setErroGlobal(null)
    try {
      await api.patch<Despesa>(`/lancamentos/despesas/${id}/aprovar`, token, {})
      setDespesas(prev => prev.map(d => d.id === id ? { ...d, status: 'aprovada' } : d))
    } catch (e) {
      setErroGlobal(e instanceof Error ? e.message : 'Erro ao aprovar despesa.')
    } finally {
      setProcessandoId(null)
    }
  }

  async function handleRejeitar(motivo: string) {
    if (!token || !rejeitandoId) return
    setProcessandoId(rejeitandoId)
    setErroGlobal(null)
    const id = rejeitandoId
    setRejeitandoId(null)
    try {
      await api.patch<Despesa>(`/lancamentos/despesas/${id}/rejeitar`, token, { motivo })
      setDespesas(prev =>
        prev.map(d => d.id === id ? { ...d, status: 'rejeitada', rejeitado_motivo: motivo } : d)
      )
    } catch (e) {
      setErroGlobal(e instanceof Error ? e.message : 'Erro ao rejeitar despesa.')
    } finally {
      setProcessandoId(null)
    }
  }

  // Drag & Drop: soltar em coluna de destino
  function handleDropAprovar() {
    if (dragId.current) { handleAprovar(dragId.current); dragId.current = null }
  }
  function handleDropRejeitar() {
    if (dragId.current) { setRejeitandoId(dragId.current); dragId.current = null }
  }

  const todas     = despesas
  const pendentes = despesas.filter(d => d.status === 'pendente')
  const aprovadas = despesas.filter(d => d.status === 'aprovada')
  const rejeitadas = despesas.filter(d => d.status === 'rejeitada')

  const somaAprovadas = aprovadas.reduce((s, d) => s + Number(d.valor), 0)

  return (
    <>
      {rejeitandoId && (
        <ModalRejeicao
          onConfirmar={handleRejeitar}
          onCancelar={() => setRejeitandoId(null)}
          loading={processandoId !== null}
        />
      )}

      <div className="flex flex-col space-y-4">
        {/* Cabeçalho */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-1.5">
              <Link href="/dashboard/lancamentos" className="text-sm text-gray-400 hover:text-gray-600">
                Lançamentos
              </Link>
              <span className="text-gray-300">/</span>
              <h1 className="text-xl font-bold text-[#071934] md:text-2xl">Aprovação de Despesas</h1>
            </div>
            <p className="mt-0.5 text-sm text-gray-500">Arraste os cards para Aprovar ou Rejeitar</p>
          </div>
          <input
            type="month"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none sm:py-1.5"
          />
        </div>

        {/* Erro global */}
        {erroGlobal && (
          <div className="flex items-center justify-between rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            <span>{erroGlobal}</span>
            <button onClick={() => setErroGlobal(null)} className="text-red-400 hover:text-red-600 ml-4">✕</button>
          </div>
        )}

        {/* Resumo rápido */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3">
          {[
            { label: 'Total Lançadas',  valor: todas.length,      extra: '',                         cor: 'bg-slate-50  border-slate-200  text-slate-700' },
            { label: 'Pendentes',       valor: pendentes.length,   extra: '',                         cor: 'bg-amber-50  border-amber-200  text-amber-800' },
            { label: 'Aprovadas',       valor: aprovadas.length,   extra: fmtBRL(somaAprovadas),      cor: 'bg-green-50  border-green-200  text-green-800' },
            { label: 'Rejeitadas',      valor: rejeitadas.length,  extra: '',                         cor: 'bg-red-50    border-red-200    text-red-800'   },
          ].map(s => (
            <div key={s.label} className={`rounded-xl border px-4 py-3 ${s.cor}`}>
              <p className="text-xs opacity-70">{s.label}</p>
              <p className="mt-1 text-xl font-bold">{s.valor}</p>
              {s.extra && <p className="text-xs opacity-60">{s.extra}</p>}
            </div>
          ))}
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#071934] border-t-transparent" />
          </div>
        ) : (
          // ── Kanban ──────────────────────────────────────────
          <div className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory sm:grid sm:grid-cols-4 sm:overflow-visible sm:pb-0">

            {/* Coluna 1 — Lançadas (todas) */}
            <KanbanColuna titulo="Lançadas" contagem={todas.length} cor="bg-slate-700" corTexto="text-white">
              {todas.length === 0
                ? <p className="py-10 text-center text-xs text-gray-400">Nenhuma despesa no período</p>
                : todas.map(d => (
                    <DespesaCard key={d.id} despesa={d} processandoId={processandoId}
                      onDragStart={(id) => { dragId.current = id }} />
                  ))
              }
            </KanbanColuna>

            {/* Coluna 2 — Pendente Aprovação */}
            <KanbanColuna titulo="Pendente Aprovação" contagem={pendentes.length} cor="bg-amber-500" corTexto="text-white">
              {pendentes.length === 0
                ? <p className="py-10 text-center text-xs text-amber-400">Nenhuma pendente 🎉</p>
                : pendentes.map(d => (
                    <DespesaCard key={d.id} despesa={d} processandoId={processandoId}
                      onAprovar={handleAprovar}
                      onIniciarRejeicao={(id) => setRejeitandoId(id)}
                      onDragStart={(id) => { dragId.current = id }}
                    />
                  ))
              }
            </KanbanColuna>

            {/* Coluna 3 — Aprovadas (drop zone) */}
            <KanbanColuna titulo="Aprovadas" contagem={aprovadas.length} cor="bg-green-600" corTexto="text-white"
              aceitaDrop onDrop={handleDropAprovar}>
              {aprovadas.length === 0
                ? <p className="py-10 text-center text-xs text-green-300">Arraste aqui para aprovar</p>
                : aprovadas.map(d => (
                    <DespesaCard key={d.id} despesa={d} processandoId={processandoId} />
                  ))
              }
            </KanbanColuna>

            {/* Coluna 4 — Rejeitadas (drop zone) */}
            <KanbanColuna titulo="Rejeitadas" contagem={rejeitadas.length} cor="bg-red-600" corTexto="text-white"
              aceitaDrop onDrop={handleDropRejeitar}>
              {rejeitadas.length === 0
                ? <p className="py-10 text-center text-xs text-red-300">Arraste aqui para rejeitar</p>
                : rejeitadas.map(d => (
                    <DespesaCard key={d.id} despesa={d} processandoId={processandoId} />
                  ))
              }
            </KanbanColuna>

          </div>
        )}
      </div>
    </>
  )
}
