'use client'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { fmtBRL, mesAnterior } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'
import type { DashboardResponse } from '@/types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

function nomeMes(inicio: string) {
  const d = new Date(inicio + 'T12:00:00')
  return `${MESES[d.getMonth()]} De ${d.getFullYear()}`
}

interface CardKPIProps {
  label: string
  valor: number | null | undefined
  sub?: string
  iconBg: string
  icon: React.ReactNode
}

function CardKPI({ label, valor, sub, iconBg, icon }: CardKPIProps) {
  return (
    <div className="flex items-start justify-between rounded-2xl bg-white p-4 shadow-sm sm:p-5">
      <div>
        <p className="text-sm font-medium text-gray-500">{label}</p>
        <p className="mt-2 text-xl font-semibold text-[#071934]">
          {valor != null ? fmtBRL(valor) : '—'}
        </p>
        {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
      </div>
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${iconBg}`}>
        {icon}
      </div>
    </div>
  )
}

// Converte **negrito** em <strong> para exibição dos insights
function renderInsight(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**')
      ? <strong key={i} className="font-semibold text-[#071934]">{p.slice(2, -2)}</strong>
      : <span key={i}>{p}</span>
  )
}

const CACHE_KEY = 'mx_insights_cache'
const CACHE_TTL_MS = 24 * 60 * 60 * 1000 // 24 horas

function lerCache(): string | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const { texto, ts } = JSON.parse(raw)
    if (Date.now() - ts > CACHE_TTL_MS) return null
    return texto as string
  } catch { return null }
}

function salvarCache(texto: string) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify({ texto, ts: Date.now() })) } catch { /* ignorar */ }
}

// ── Componente de Insights do Mercado ─────────────────────────
function InsightsMercado({ token, trigger }: { token: string; trigger: number }) {
  const [texto, setTexto] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const isFirstLoad = useRef(true)

  useEffect(() => {
    if (!token) return

    // Na primeira carga, verifica cache — só busca se vencido
    const forcar = !isFirstLoad.current
    isFirstLoad.current = false

    if (!forcar) {
      const cached = lerCache()
      if (cached) {
        setTexto(cached)
        setCarregando(false)
        return
      }
    }

    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    setTexto('')
    setErro(false)
    setCarregando(true)

    ;(async () => {
      try {
        const res = await fetch(`${BASE}/dashboard/insights`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: ctrl.signal,
        })
        if (!res.ok || !res.body) throw new Error()

        const reader = res.body.getReader()
        const dec = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          for (const line of dec.decode(value, { stream: true }).split('\n')) {
            if (!line.startsWith('data: ')) continue
            try {
              const p = JSON.parse(line.slice(6))
              if (p.fim) break
              if (p.erro) { setErro(true); break }
              if (p.conteudo) {
                buffer += p.conteudo
                setTexto(buffer)
              }
            } catch { /* linha parcial */ }
          }
        }
        if (buffer) salvarCache(buffer)
      } catch (e: unknown) {
        if (e instanceof Error && e.name !== 'AbortError') setErro(true)
      } finally {
        setCarregando(false)
      }
    })()

    return () => ctrl.abort()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, trigger])

  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm sm:p-5">
      {/* Cabeçalho */}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4 text-amber-600">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold text-[#071934]">Mercado de Seguros</p>
          <p className="text-[10px] text-gray-400">Análise em tempo real · Fontes públicas + IA</p>
        </div>
        {carregando && (
          <span className="ml-auto flex gap-1">
            {[0, 0.15, 0.3].map((d, i) => (
              <span key={i} className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-bounce"
                style={{ animationDelay: `${d}s` }} />
            ))}
          </span>
        )}
      </div>

      {/* Conteúdo */}
      {erro ? (
        <p className="text-xs text-gray-400">Não foi possível carregar os insights agora. Tente atualizar.</p>
      ) : texto ? (
        <div className="space-y-3">
          {texto.split('\n').filter(l => l.trim()).map((linha, i) => (
            <p key={i} className={`text-xs leading-relaxed ${linha.startsWith('**') ? 'text-gray-800' : 'text-gray-500'}`}>
              {renderInsight(linha)}
            </p>
          ))}
        </div>
      ) : carregando ? (
        <div className="space-y-2">
          {[1, 0.75, 0.9, 0.6].map((w, i) => (
            <div key={i} className="h-3 animate-pulse rounded bg-gray-100" style={{ width: `${w * 100}%` }} />
          ))}
        </div>
      ) : null}
    </div>
  )
}

const IconTrendUp = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-blue-600">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
  </svg>
)
const IconDollar = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-green-600">
    <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
  </svg>
)
const IconTarget = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-purple-500">
    <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>
  </svg>
)
const IconRefresh = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
    <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
  </svg>
)

export default function DashboardPage() {
  const { token } = useAuth()
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [insightsTrigger, setInsightsTrigger] = useState(0)

  const buscar = useCallback(() => {
    if (!token) return
    setLoading(true)
    setErro(null)
    const [inicio, fim] = mesAnterior()
    api.get<DashboardResponse>(`/dashboard?inicio=${inicio}&fim=${fim}`, token)
      .then(setData)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false))
  }, [token])

  function atualizar() {
    buscar()
    setInsightsTrigger(t => t + 1)
  }

  useEffect(() => { buscar() }, [buscar])

  const d = data?.dre
  const periodo = data ? nomeMes(data.periodo.inicio) : ''

  return (
    <div className="space-y-6">
      {/* Cabeçalho */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[#071934] md:text-2xl">Visão Geral</h1>
          {!loading && periodo && (
            <p className="mt-0.5 text-sm text-gray-500">{periodo}</p>
          )}
        </div>
        <button
          onClick={atualizar}
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-medium text-gray-600 shadow-sm hover:bg-gray-50"
        >
          <IconRefresh /> Atualizar
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} variant="card" />
          ))}
        </div>
      ) : erro ? (
        <div className="rounded-xl bg-red-50 p-4 text-sm text-red-600">{erro}</div>
      ) : d ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <CardKPI
              label="Receita Bruta"
              valor={d.receita_bruta}
              sub="Competência"
              iconBg="bg-blue-50"
              icon={<IconTrendUp />}
            />
            <CardKPI
              label="Receita Líquida"
              valor={d.receita_liquida}
              iconBg="bg-green-50"
              icon={<IconDollar />}
            />
            <CardKPI
              label="EBITDA"
              valor={d.ebitda}
              iconBg="bg-purple-50"
              icon={<IconTarget />}
            />
          </div>

          <p className="text-xs text-gray-400">
            Campos exibidos conforme seu perfil de acesso. &quot;—&quot; indica informação não disponível para seu perfil.
          </p>

          {/* Insights do mercado de seguros */}
          {token && <InsightsMercado token={token} trigger={insightsTrigger} />}

          {/* Alertas */}
          {data?.alertas && data.alertas.length > 0 && (
            <div className="space-y-2">
              {data.alertas.map((a, i) => (
                <div key={i} className={`rounded-xl px-4 py-3 text-sm ${
                  a.severidade === 'critico' ? 'bg-red-50 text-red-700' :
                  a.severidade === 'aviso'   ? 'bg-amber-50 text-amber-700' :
                                               'bg-blue-50 text-blue-700'
                }`}>
                  {a.mensagem}
                </div>
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
