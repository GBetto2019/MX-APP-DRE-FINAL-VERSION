import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function fmtBRL(valor: number | null | undefined): string {
  if (valor == null) return '—'
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor)
}

export function fmtPct(valor: number | null | undefined): string {
  if (valor == null) return '—'
  return `${valor.toFixed(1).replace('.', ',')}%`
}

export function primeiroUltimoDia(ano: number, mes: number): [string, string] {
  const inicio = `${ano}-${String(mes).padStart(2, '0')}-01`
  const fim = new Date(ano, mes, 0)
  const fimStr = `${ano}-${String(mes).padStart(2, '0')}-${String(fim.getDate()).padStart(2, '0')}`
  return [inicio, fimStr]
}

export function mesAnterior(): [string, string] {
  const hoje = new Date()
  const ano = hoje.getMonth() === 0 ? hoje.getFullYear() - 1 : hoje.getFullYear()
  const mes = hoje.getMonth() === 0 ? 12 : hoje.getMonth()
  return primeiroUltimoDia(ano, mes)
}

export function mesAtual(): [string, string] {
  const hoje = new Date()
  return primeiroUltimoDia(hoje.getFullYear(), hoje.getMonth() + 1)
}
