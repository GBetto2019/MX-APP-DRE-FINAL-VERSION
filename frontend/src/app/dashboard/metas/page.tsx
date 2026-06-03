'use client'
import { useEffect, useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { fmtBRL, fmtPct } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'
import type { MetasResponse } from '@/types'

export default function MetasPage() {
  const { token } = useAuth()
  const hoje = new Date()
  const [mes, setMes] = useState(`${hoje.getFullYear()}-${String(hoje.getMonth()+1).padStart(2,'0')}`)
  const [data, setData] = useState<MetasResponse | null>(null)
  const [loading, setLoading] = useState(true)

  function buscar() {
    if (!token) return
    setLoading(true)
    api.get<MetasResponse>(`/metas?competencia=${mes}-01`, token)
      .then(setData).catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => { buscar() }, [token]) // eslint-disable-line

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-bold text-[#071934] md:text-2xl">Metas</h1>
        <div className="flex items-center gap-2">
          <input type="month" value={mes} onChange={(e) => setMes(e.target.value)}
            className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none sm:flex-none sm:py-1.5" />
          <button onClick={buscar} className="rounded-lg bg-[#071934] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#0E2444] sm:py-2">Consultar</button>
        </div>
      </div>

      {loading ? (
        <Skeleton variant="table" className="h-48" />
      ) : (
        <div className="rounded-2xl bg-white p-6 shadow-sm space-y-5">
          {(data?.items ?? []).length === 0 ? (
            <p className="text-center py-8 text-sm text-gray-400">Nenhuma meta cadastrada para o período</p>
          ) : (
            (data?.items ?? []).map((meta) => (
              <div key={meta.meta_id}>
                <div className="flex items-center justify-between mb-1.5">
                  <div>
                    <span className="text-sm font-medium text-gray-700 capitalize">
                      {meta.metrica.replace(/_/g, ' ')}
                    </span>
                    <span className="ml-2 text-xs text-gray-400 capitalize">({meta.escopo})</span>
                  </div>
                  <div className="text-right">
                    <span className={`text-sm font-semibold ${meta.atingida ? 'text-green-600' : 'text-[#071934]'}`}>
                      {fmtPct(meta.percentual)}
                    </span>
                    <span className="ml-2 text-xs text-gray-400">
                      {fmtBRL(meta.valor_atual)} / {fmtBRL(meta.valor_alvo)}
                    </span>
                  </div>
                </div>
                <div className="h-2 w-full rounded-full bg-gray-100">
                  <div
                    className={`h-2 rounded-full transition-all ${meta.atingida ? 'bg-green-500' : 'bg-[#071934]'}`}
                    style={{ width: `${Math.min(meta.percentual, 100)}%` }}
                  />
                </div>
                {meta.atingida && (
                  <p className="mt-1 text-xs text-green-600 font-medium">✓ Meta atingida</p>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}


