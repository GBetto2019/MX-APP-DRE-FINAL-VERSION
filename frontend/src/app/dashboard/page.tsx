'use client'
import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { fmtBRL, mesAnterior } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'
import type { DashboardResponse } from '@/types'

const MESES = ['Janeiro','Fevereiro','MarÃ§o','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

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
    <div className="flex items-start justify-between rounded-2xl bg-white p-5 shadow-sm">
      <div>
        <p className="text-sm font-medium text-gray-500">{label}</p>
        <p className="mt-2 text-lg font-semibold text-[#071934]">
          {valor != null ? fmtBRL(valor) : 'â€”'}
        </p>
        {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
      </div>
      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconBg}`}>
        {icon}
      </div>
    </div>
  )
}

const IconTrendUp = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-blue-600">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
  </svg>
)
const IconTrendDown = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-red-500">
    <polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/>
  </svg>
)
const IconDollar = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-green-600">
    <line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
  </svg>
)
const IconBar = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5 text-amber-600">
    <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
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

  useEffect(() => { buscar() }, [buscar])

  const d = data?.dre
  const periodo = data ? nomeMes(data.periodo.inicio) : ''

  return (
    <div className="space-y-6">
      {/* CabeÃ§alho */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#071934]">VisÃ£o Geral</h1>
          {!loading && periodo && (
            <p className="mt-0.5 text-sm text-gray-500">{periodo}</p>
          )}
        </div>
        <button
          onClick={buscar}
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 shadow-sm hover:bg-gray-50"
        >
          <IconRefresh /> Atualizar
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="card" />
          ))}
        </div>
      ) : erro ? (
        <div className="rounded-xl bg-red-50 p-4 text-sm text-red-600">{erro}</div>
      ) : d ? (
        <>
          <div className="grid grid-cols-3 gap-4">
            <CardKPI
              label="Receita Bruta"
              valor={d.receita_bruta}
              sub="CompetÃªncia"
              iconBg="bg-blue-50"
              icon={<IconTrendUp />}
            />
            <CardKPI
              label="Estornos"
              valor={d.estornos}
              iconBg="bg-red-50"
              icon={<IconTrendDown />}
            />
            <CardKPI
              label="Receita LÃ­quida"
              valor={d.receita_liquida}
              iconBg="bg-green-50"
              icon={<IconDollar />}
            />
            <CardKPI
              label="Repasses"
              valor={d.repasses_produtores}
              iconBg="bg-amber-50"
              icon={<IconBar />}
            />
            <CardKPI
              label="EBITDA"
              valor={d.ebitda}
              iconBg="bg-purple-50"
              icon={<IconTarget />}
            />
            <CardKPI
              label="Resultado LÃ­quido"
              valor={d.resultado_liquido}
              iconBg="bg-green-50"
              icon={<IconDollar />}
            />
          </div>

          <p className="text-xs text-gray-400">
            Campos exibidos conforme seu perfil de acesso. &quot;â€”&quot; indica informaÃ§Ã£o nÃ£o disponÃ­vel para seu perfil.
          </p>

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


