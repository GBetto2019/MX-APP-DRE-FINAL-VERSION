'use client'
import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { fmtBRL, mesAnterior } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'

interface RepasseItem {
  id: string; produtor_nome: string | null; valor: number
  percentual: number | null; competencia: string; pago_em: string | null; status: string
}
interface RepassesResp { total: number; items: RepasseItem[]; soma_previsto: number; soma_pago: number }

const STATUS_COR: Record<string, string> = {
  pago:     'bg-green-100 text-green-700',
  pendente: 'bg-amber-100 text-amber-700',
  default:  'bg-gray-100 text-gray-600',
}

export default function RepassesPage() {
  const { token } = useAuth()
  const [inicio, setInicio] = useState(mesAnterior()[0])
  const [fim, setFim]     = useState(mesAnterior()[1])
  const [data, setData]   = useState<RepassesResp | null>(null)
  const [loading, setLoading] = useState(true)

  const buscar = useCallback(() => {
    if (!token) return
    setLoading(true)
    api.get<RepassesResp>(`/repasses?inicio=${inicio}&fim=${fim}`, token)
      .then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [token, inicio, fim])

  useEffect(() => { buscar() }, [buscar])

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <h1 className="text-xl font-bold text-[#071934] md:text-2xl">Repasses</h1>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span className="shrink-0">De</span>
            <input type="month" value={inicio.slice(0,7)}
              onChange={(e) => { const [y,m]=e.target.value.split('-'); setInicio(`${y}-${m}-01`) }}
              className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none" />
            <span className="shrink-0">Até</span>
            <input type="month" value={fim.slice(0,7)}
              onChange={(e) => { const [y,m]=e.target.value.split('-'); const l=new Date(+y,+m,0).getDate(); setFim(`${y}-${m}-${l}`) }}
              className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:outline-none" />
          </div>
          <button onClick={buscar} className="w-full rounded-lg bg-[#071934] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#0E2444] sm:w-auto">Consultar</button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <p className="text-xs text-gray-500">Total Previsto</p>
          <p className="mt-1 text-xl font-bold text-[#071934]">{fmtBRL(data?.soma_previsto ?? 0)}</p>
        </div>
        <div className="rounded-2xl bg-white p-5 shadow-sm">
          <p className="text-xs text-gray-500">Total Pago</p>
          <p className="mt-1 text-xl font-bold text-green-600">{fmtBRL(data?.soma_pago ?? 0)}</p>
        </div>
      </div>

      <div className="rounded-2xl bg-white shadow-sm overflow-hidden">
        {loading ? <div className="p-5"><Skeleton variant="table" /></div> : (
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                <th className="px-5 py-3">Produtor</th>
                <th className="px-5 py-3">Competência</th>
                <th className="px-5 py-3 text-right">Valor</th>
                <th className="px-5 py-3">Pago em</th>
                <th className="px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((r) => (
                <tr key={r.id} className="border-t border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3 font-medium">{r.produtor_nome ?? '—'}</td>
                  <td className="px-5 py-3 text-gray-500">{r.competencia}</td>
                  <td className="px-5 py-3 text-right tabular-nums font-medium">{fmtBRL(r.valor)}</td>
                  <td className="px-5 py-3 text-gray-400">{r.pago_em ?? '—'}</td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COR[r.status] ?? STATUS_COR.default}`}>
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
              {(data?.items ?? []).length === 0 && (
                <tr><td colSpan={5} className="py-10 text-center text-sm text-gray-400">Nenhum repasse no período</td></tr>
              )}
            </tbody>
          </table></div>
        )}
      </div>
    </div>
  )
}


