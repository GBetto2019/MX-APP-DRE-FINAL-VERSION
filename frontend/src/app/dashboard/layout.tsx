'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { api } from '@/lib/api'
import { Sidebar } from '@/components/layout/Sidebar'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import type { Usuario } from '@/types'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { session, loading, token, signOut } = useAuth()
  const router = useRouter()
  const [usuario, setUsuario] = useState<Usuario | null>(null)

  useEffect(() => {
    if (!loading && !session) router.replace('/login')
  }, [loading, session, router])

  useEffect(() => {
    if (!token) return
    api.get<Usuario>('/usuarios/me', token)
      .then(setUsuario)
      .catch(() => {})
  }, [token])

  async function handleSignOut() {
    await signOut()
    router.push('/login')
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#F0F2F5]">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#071934] border-t-transparent" />
      </div>
    )
  }

  if (!session) return null

  const role = usuario?.role ?? 'comercial'
  const email = usuario?.email ?? session.user.email ?? ''
  const nome = usuario?.nome ?? ''

  return (
    <div className="flex h-screen overflow-hidden bg-[#F0F2F5]">
      <Sidebar role={role} email={email} nome={nome} onSignOut={handleSignOut} />
      <main className="flex-1 overflow-auto p-8">
        <ErrorBoundary>
          {children}
        </ErrorBoundary>
      </main>
    </div>
  )
}
