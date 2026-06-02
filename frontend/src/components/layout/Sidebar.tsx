'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import type { Role } from '@/types'

import Image from 'next/image'

/* ── Ícones SVG inline ─────────────────────────────── */
const Icon = {
  grid:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>,
  chart:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  book:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>,
  wave:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>,
  target: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>,
  arrows: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>,
  chat:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
  download: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
  gear:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  chevron:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4"><polyline points="15 18 9 12 15 6"/></svg>,
  users:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
}

interface NavItem { href: string; label: string; icon: React.ReactNode; roles?: Role[] }

const NAV: NavItem[] = [
  { href: '/dashboard',              label: 'Visão Geral',   icon: Icon.grid },
  { href: '/dashboard/dre',         label: 'DRE',           icon: Icon.chart },
  { href: '/dashboard/lancamentos', label: 'Lançamentos',   icon: Icon.book },
  { href: '/dashboard/estornos',    label: 'Estornos',      icon: Icon.wave },
  { href: '/dashboard/metas',       label: 'Metas',         icon: Icon.target },
  { href: '/dashboard/repasses',    label: 'Repasses',      icon: Icon.arrows },
  { href: '/dashboard/exports',     label: 'Exportações',   icon: Icon.download },
  { href: '/dashboard/assistente',  label: 'Assistente IA', icon: Icon.chat },
]

const NAV_BOTTOM: NavItem[] = [
  { href: '/dashboard/configuracoes',   label: 'Configurações',icon: Icon.gear },
  { href: '/dashboard/usuarios',        label: 'Usuários',     icon: Icon.users, roles: ['admin'] },
]

interface Props { role: Role; email: string; nome: string; onSignOut: () => void }

export function Sidebar({ role, email, nome, onSignOut }: Props) {
  const pathname = usePathname()

  const isActive = (href: string) =>
    href === '/dashboard' ? pathname === '/dashboard' : pathname.startsWith(href)

  const visible = (item: NavItem) => !item.roles || item.roles.includes(role)

  return (
    <aside className="relative flex h-screen w-[240px] shrink-0 flex-col bg-[#071934]">
      {/* Botão recolher (decorativo — pode implementar depois) */}
      <button className="absolute -right-3 top-20 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-[#1a3a5c] bg-[#071934] text-white/60 hover:text-white">
        {Icon.chevron}
      </button>

      {/* Logo */}
      <div className="flex items-center justify-center border-b border-white/10 px-6 py-5">
        <Image src="/logo_white.png" alt="MX Corretora de Seguros" width={140} height={48} className="object-contain" />
      </div>

      {/* Nav principal */}
      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {NAV.filter(visible).map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
              isActive(item.href)
                ? 'bg-white/15 text-white'
                : 'text-white/60 hover:bg-white/8 hover:text-white/90',
            )}
          >
            <span className={isActive(item.href) ? 'text-white' : 'text-white/50'}>
              {item.icon}
            </span>
            {item.label}
          </Link>
        ))}
      </nav>

      {/* Nav inferior */}
      <div className="border-t border-white/10 px-3 py-3">
        {NAV_BOTTOM.filter(visible).map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
              isActive(item.href)
                ? 'bg-white/15 text-white'
                : 'text-white/60 hover:bg-white/8 hover:text-white/90',
            )}
          >
            <span className="text-white/50">{item.icon}</span>
            {item.label}
          </Link>
        ))}

        {/* Usuário */}
        <div className="mt-3 border-t border-white/10 pt-3">
          <p className="px-3 text-xs font-medium text-beige truncate">{email}</p>
          <button
            onClick={onSignOut}
            className="mt-1 flex w-full items-center gap-1 rounded-lg px-3 py-1.5 text-xs text-white/40 hover:text-white/70"
          >
            Sair
          </button>
        </div>
      </div>
    </aside>
  )
}
