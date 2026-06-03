'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import type { Role } from '@/types'
import Image from 'next/image'

const Icon = {
  grid:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>,
  kanban:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4"><rect x="3" y="3" width="5" height="18" rx="1"/><rect x="10" y="3" width="5" height="12" rx="1"/><rect x="17" y="3" width="5" height="8" rx="1"/></svg>,
  chart:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  book:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>,
  chat:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
  download:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
  gear:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  faq:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>,
  users:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-4 w-4"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
}

interface NavItem { href: string; label: string; icon: React.ReactNode; roles?: Role[] }

const NAV: NavItem[] = [
  { href: '/dashboard',                        label: 'Visão Geral',   icon: Icon.grid     },
  { href: '/dashboard/dre',                    label: 'DRE',           icon: Icon.chart    },
  { href: '/dashboard/lancamentos',            label: 'Lançamentos',   icon: Icon.book     },
  { href: '/dashboard/lancamentos/aprovacoes', label: 'Aprovações',    icon: Icon.kanban,  roles: ['admin', 'gestor'] },
  { href: '/dashboard/exports',                label: 'Exportações',   icon: Icon.download },
  { href: '/dashboard/assistente',             label: 'Assistente IA', icon: Icon.chat     },
]

const NAV_BOTTOM: NavItem[] = [
  { href: '/dashboard/ajuda',         label: 'FAQ',           icon: Icon.faq                              },
  { href: '/dashboard/configuracoes', label: 'Configurações', icon: Icon.gear, roles: ['admin', 'gestor'] },
]

interface Props {
  role: Role
  email: string
  nome: string
  onSignOut: () => void
  aberta?: boolean
  onFechar?: () => void
}

export function Sidebar({ role, email, nome, onSignOut, aberta = false, onFechar }: Props) {
  const pathname = usePathname()

  const isActive = (href: string) =>
    href === '/dashboard' ? pathname === '/dashboard' : pathname.startsWith(href)

  const visible = (item: NavItem) => !item.roles || item.roles.includes(role)

  const navItemCls = (active: boolean) => cn(
    'flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors',
    active
      ? 'bg-white/15 text-white'
      : 'text-white/55 hover:bg-white/8 hover:text-white/90',
  )

  const visibleBottom = NAV_BOTTOM.filter(visible)

  return (
    <>
      {/* Overlay mobile */}
      {aberta && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onFechar}
        />
      )}

      <aside className={cn(
        'fixed inset-y-0 left-0 z-50 flex h-full w-[220px] shrink-0 flex-col bg-[#071934] transition-transform duration-200 ease-in-out',
        'lg:relative lg:z-auto lg:translate-x-0',
        aberta ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
      )}>
        {/* Logo */}
        <div className="flex items-center justify-center border-b border-white/10 px-5 py-3">
          <Image src="/logo_beige.png" alt="MX Corretora de Seguros" width={120} height={40} className="object-contain" />
        </div>

        {/* Nav principal */}
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
          {NAV.filter(visible).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={onFechar}
              className={navItemCls(isActive(item.href))}
            >
              <span className={isActive(item.href) ? 'text-white' : 'text-white/45'}>
                {item.icon}
              </span>
              {item.label}
            </Link>
          ))}
        </nav>

        {/* Nav inferior */}
        <div className="border-t border-white/10 px-2 py-2">
          {visibleBottom.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={onFechar}
              className={navItemCls(isActive(item.href))}
            >
              <span className={isActive(item.href) ? 'text-white' : 'text-white/45'}>
                {item.icon}
              </span>
              {item.label}
            </Link>
          ))}

          {/* Perfil */}
          <div className={cn('px-3 py-2', visibleBottom.length > 0 && 'mt-1 border-t border-white/10 pt-2')}>
            <p className="truncate text-[11px] text-[#B5A882] leading-tight">{email}</p>
            <button
              onClick={onSignOut}
              className="mt-1 text-[11px] text-white/35 hover:text-white/60 transition-colors"
            >
              Sair
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
