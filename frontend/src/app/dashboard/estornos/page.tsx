'use client'
import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { fmtBRL, mesAnterior } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'

interface EstornoItem {
  id: string; apolice_id: string; seguradora_nome: string | null
  valor: number; motivo: string | null
  competencia_original: string; competencia_estorno: string
}
interface EstornosResp { total: number; items: EstornoItem[]; soma_total: number; taxa_estorno: number; alerta_5pct: boolean }

export default function EstornosPage() {
  const { token } = useAuth()
  const [inicio, setInicio] = useState(mesAnterior()[0])
  const [fim, setFim]     = useState(mesAnterior()[1])
  const [data, setData]   = useState<EstornosResp | null>(null)
  const [loading, setLoading] = useState(true)

  const buscar = useCallback(() => {
    if (!token) return
    setLoading(true)
    api.get<EstornosResp>(`/estornos?inicio=${inicio}&fim=${fim}`, token)
      .then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [token, inicio, fim])

  useEffect(() => { buscar() }, [buscar])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-[#071934]">Estornos</h1>
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <span>De</span>
          <input type="month" value={inicio.slice(0,7)}
            onChange={(e) => { const [y,m]=e.target.value.split('-'); setInicio(`${y}-${m}-01`) }}
            className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 focus:outline-none" />
          <span>Até</span>
          <input type="month" value={fim.slice(0,7)}
            onChange={(e) => { const [y,m]=e.target.value.split('-'); const l=new Date(+y,+m,0).getDate(); setFim(`${y}-${m}-${l}`) }}
            className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 focus:outline-none" />
          <button onClick={buscar} className="rounded-lg bg-[#071934] px-4 py-2 text-sm font-medium text-white hover:bg-[#0E2444]">Consultar</button>
        </div>
      </div>

      {data?.alerta_5pct && (
        <div className="rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
          ⚠ Taxa de estorno acima de 5% ({(data.taxa_estorno * 100).toFixed(1)}%)
        </div>
      )}

      <div className="rounded-2xl bg-white shadow-sm overflow-hidden">
        {loading ? <div className="p-5"><Skeleton variant="table" /></div> : (
          <>
            <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
              <span className="text-sm font-medium text-gray-700">{data?.total ?? 0} estorno(s)</span>
              <span className="text-sm font-bold text-red-500">{fmtBRL(data?.soma_total ?? 0)}</span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-left text-xs font-medium text-gray-500">
                  <th className="px-5 py-3">Seguradora</th>
                  <th className="px-5 py-3">Competência Original</th>
                  <th className="px-5 py-3">Competência Estorno</th>
                  <th className="px-5 py-3">Motivo</th>
                  <th className="px-5 py-3 text-right">Valor</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((e) => (
                  <tr key={e.id} className="border-t border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 font-medium">{e.seguradora_nome ?? '—'}</td>
                    <td className="px-5 py-3 text-gray-500">{e.competencia_original}</td>
                    <td className="px-5 py-3 text-gray-500">{e.competencia_estorno}</td>
                    <td className="px-5 py-3 text-gray-500">{e.motivo ?? '—'}</td>
                    <td className="px-5 py-3 text-right font-medium text-red-500 tabular-nums">{fmtBRL(e.valor)}</td>
                  </tr>
                ))}
                {(data?.items ?? []).length === 0 && (
                  <tr><td colSpan={5} className="py-10 text-center text-sm text-gray-400">Nenhum estorno no período</td></tr>
                )}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}


