'use client'
import { useEffect, useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { fmtBRL, mesAnterior } from '@/lib/utils'
import { Skeleton } from '@/components/ui/Skeleton'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { DREResponse, LinhasDRE } from '@/types'

interface ReceitaRamo { ramo_nome: string; receita_total: number }
interface ReceitaRamoResponse { items: ReceitaRamo[]; total: number }

const LINHAS: { key: keyof LinhasDRE; label: string; total?: boolean; deducao?: boolean }[] = [
  { key: 'receita_bruta',             label: 'Receita Bruta',             total: true },
  { key: 'estornos',                  label: '(-) Estornos',              deducao: true },
  { key: 'impostos',                  label: '(-) Impostos',              deducao: true },
  { key: 'receita_liquida',           label: '= Receita Líquida',         total: true },
  { key: 'repasses_produtores',       label: '(-) Repasses Produtores',   deducao: true },
  { key: 'margem_contribuicao',       label: '= Margem de Contribuição',  total: true },
  { key: 'despesas_fixas',            label: '(-) Despesas Fixas',        deducao: true },
  { key: 'ebitda',                    label: '= EBITDA',                  total: true },
  { key: 'despesas_nao_operacionais', label: '(-) Desp. Não Operacionais',deducao: true },
  { key: 'resultado_liquido',         label: '= Resultado Líquido',       total: true },
]

function DateInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-500">{label}</span>
      <input
        type="month"
        value={value.slice(0, 7)}
        onChange={(e) => {
          const [y, m] = e.target.value.split('-')
          const lastDay = new Date(Number(y), Number(m), 0).getDate()
          onChange(label === 'De' ? `${y}-${m}-01` : `${y}-${m}-${lastDay}`)
        }}
        className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 focus:border-[#071934] focus:outline-none"
      />
    </div>
  )
}

export default function DrePage() {
  const { token } = useAuth()
  const [[inicio, fim], setPeriodo] = useState(mesAnterior())
  const [dre, setDre] = useState<DREResponse | null>(null)
  const [ramos, setRamos] = useState<ReceitaRamo[]>([])
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  function buscar() {
    if (!token) return
    setLoading(true); setErro(null)
    Promise.all([
      api.get<DREResponse>(`/dre?inicio=${inicio}&fim=${fim}`, token),
      api.get<ReceitaRamoResponse>(`/comissoes/receita-por-ramo?inicio=${inicio}&fim=${fim}`, token),
    ])
      .then(([d, r]) => { setDre(d); setRamos(r.items ?? []) })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { buscar() }, [token]) // eslint-disable-line

  return (
    <div className="space-y-6">
      {/* Cabeçalho */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-[#071934]">DRE</h1>
        <div className="flex items-center gap-4">
          <DateInput label="De"  value={inicio} onChange={(v) => setPeriodo([v, fim])} />
          <DateInput label="Até" value={fim}    onChange={(v) => setPeriodo([inicio, v])} />
          <button onClick={buscar} className="rounded-lg bg-[#071934] px-4 py-2 text-sm font-medium text-white hover:bg-[#0E2444]">
            Consultar
          </button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-4">
          <Skeleton variant="table" className="h-80" />
          <Skeleton variant="card" className="h-80" />
        </div>
      ) : erro ? (
        <p className="rounded-xl bg-red-50 p-4 text-sm text-red-600">{erro}</p>
      ) : dre ? (
        <div className="grid grid-cols-2 gap-4">
          {/* Tabela DRE */}
          <div className="rounded-2xl bg-white p-6 shadow-sm">
            <h2 className="mb-4 font-semibold text-[#071934]">Demonstração de Resultados</h2>
            <table className="w-full text-sm">
              <tbody>
                {LINHAS.map(({ key, label, total, deducao }) => {
                  const valor = dre.dre[key]
                  if (valor == null) return null
                  const negativo = valor < 0
                  return (
                    <tr
                      key={key}
                      className={total ? 'border-t-2 border-gray-100' : ''}
                    >
                      <td className={`py-2 pr-4 ${total ? 'font-semibold text-[#071934]' : 'pl-3 text-gray-600'}`}>
                        {label}
                      </td>
                      <td className={`py-2 text-right tabular-nums font-${total ? 'semibold' : 'normal'} ${
                        deducao || negativo ? 'text-red-500' : total ? 'text-[#071934]' : 'text-gray-700'
                      }`}>
                        {deducao && valor !== 0 ? `R$ ${Math.abs(valor).toLocaleString('pt-BR', {minimumFractionDigits:2})}` : fmtBRL(valor)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Gráfico receita por ramo */}
          <div className="rounded-2xl bg-white p-6 shadow-sm">
            <h2 className="mb-4 font-semibold text-[#071934]">Receita por Ramo</h2>
            {ramos.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={ramos} margin={{ left: -10 }}>
                  <XAxis dataKey="ramo_nome" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `R$${(v/1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v: number) => fmtBRL(v)} />
                  <Bar dataKey="receita_total" fill="#071934" radius={[4,4,0,0]} name="Receita" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-64 items-center justify-center text-sm text-gray-400">
                Sem dados de receita por ramo no período
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}


