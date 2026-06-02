'use client'
import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { mesAnterior } from '@/lib/utils'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export default function ExportsPage() {
  const { token } = useAuth()
  const [inicio, setInicio] = useState(mesAnterior()[0])
  const [fim, setFim] = useState(mesAnterior()[1])
  const [loading, setLoading] = useState<'pdf' | 'xlsx' | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  async function baixar(tipo: 'pdf' | 'xlsx') {
    if (!token) return
    setLoading(tipo)
    setErro(null)
    try {
      const res = await fetch(
        `${BASE}/exports/dre/${tipo}?inicio=${inicio}&fim=${fim}`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail ?? `HTTP ${res.status}`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `DRE_MX_${inicio}_${fim}.${tipo}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Erro ao exportar')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-mx-navy">ExportaÃ§Ãµes</h1>

      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-5">
        <h2 className="font-semibold text-gray-800">Exportar DRE</h2>

        <div className="flex flex-wrap gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600">InÃ­cio</label>
            <input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)}
              className="mt-1 rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-mx-blue focus:outline-none" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600">Fim</label>
            <input type="date" value={fim} onChange={(e) => setFim(e.target.value)}
              className="mt-1 rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-mx-blue focus:outline-none" />
          </div>
        </div>

        {erro && <p className="text-sm text-red-600">Erro: {erro}</p>}

        <div className="flex gap-3">
          <button
            onClick={() => baixar('xlsx')}
            disabled={!!loading}
            className="rounded-lg border border-mx-navy px-5 py-2 text-sm font-medium text-mx-navy hover:bg-mx-light disabled:opacity-50"
          >
            {loading === 'xlsx' ? 'Gerandoâ€¦' : 'â¬‡ Excel (.xlsx)'}
          </button>
          <button
            onClick={() => baixar('pdf')}
            disabled={!!loading}
            className="rounded-lg bg-mx-navy px-5 py-2 text-sm font-medium text-white hover:bg-mx-blue disabled:opacity-50"
          >
            {loading === 'pdf' ? 'Gerandoâ€¦' : 'â¬‡ PDF'}
          </button>
        </div>
      </div>
    </div>
  )
}


