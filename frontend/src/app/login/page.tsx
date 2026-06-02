'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { useAuth } from '@/hooks/useAuth'

export default function LoginPage() {
  const { signIn } = useAuth()
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErro(null)
    setLoading(true)
    const { error } = await signIn(email, senha)
    if (error) {
      setErro('E-mail ou senha invÃ¡lidos.')
      setLoading(false)
    } else {
      router.push('/dashboard')
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Painel esquerdo â€” branding */}
      <div className="relative hidden w-[52%] flex-col justify-between overflow-hidden bg-[#071934] p-10 lg:flex">
        {/* CÃ­rculos decorativos */}
        <div className="absolute -right-24 -top-24 h-[420px] w-[420px] rounded-full bg-[#0a2040] opacity-70" />
        <div className="absolute -bottom-32 -right-10 h-[500px] w-[500px] rounded-full bg-[#0a2040] opacity-60" />

        {/* Logo */}
        <div className="relative z-10">
          <Image src="/logo_beige.png" alt="MX Corretora de Seguros" width={180} height={60} className="object-contain" />
        </div>

        {/* Texto central */}
        <div className="relative z-10 max-w-md">
          <h1 className="text-4xl font-bold leading-tight text-white">
            GestÃ£o financeira{' '}
            <span className="text-beige">inteligente</span>
            <br />em tempo real
          </h1>
          <p className="mt-4 text-base leading-relaxed text-blue-200/70">
            DRE atualizado, lanÃ§amentos organizados por banco e centro de custo, e um assistente
            com IA pronto para responder suas dÃºvidas.
          </p>
        </div>

        {/* RodapÃ© */}
        <p className="relative z-10 text-sm text-blue-200/40">
          Â© 2026 MX Corretora de Seguros
        </p>
      </div>

      {/* Painel direito â€” formulÃ¡rio */}
      <div className="flex flex-1 flex-col bg-[#F0F2F5]">
        <div className="flex flex-1 items-center justify-center px-8">
          <div className="w-full max-w-sm">
            <div className="rounded-2xl bg-white p-8 shadow-sm">
              <h2 className="text-2xl font-bold text-[#071934]">Bem-vindo!</h2>
              <p className="mt-1 text-sm text-gray-500">Acesse com as suas credenciais</p>

              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500">
                    E-MAIL
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="seu@mxseguros.com.br"
                    className="mt-1.5 block w-full rounded-lg border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:border-[#071934] focus:outline-none focus:ring-1 focus:ring-[#071934]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500">
                    SENHA
                  </label>
                  <input
                    type="password"
                    required
                    value={senha}
                    onChange={(e) => setSenha(e.target.value)}
                    placeholder="â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢"
                    className="mt-1.5 block w-full rounded-lg border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:border-[#071934] focus:outline-none focus:ring-1 focus:ring-[#071934]"
                  />
                </div>

                {erro && (
                  <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{erro}</p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="mt-2 w-full rounded-xl bg-[#071934] py-3 text-sm font-semibold text-white transition hover:bg-[#0E2444] disabled:opacity-60"
                >
                  {loading ? 'Entrandoâ€¦' : 'Entrar no sistema'}
                </button>
              </form>

              <p className="mt-5 text-center text-xs text-beige">
                NÃ£o tem acesso? Fale com o administrador do sistema.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}


