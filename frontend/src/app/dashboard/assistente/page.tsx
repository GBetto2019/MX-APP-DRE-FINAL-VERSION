'use client'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import type { ChatMensagem } from '@/types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const BotIcon = () => (
  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#071934] text-white text-xs">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
      <rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/>
      <path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/>
    </svg>
  </div>
)
const UserIcon = () => (
  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-200 text-gray-500">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
    </svg>
  </div>
)

const MSG_BOAS_VINDAS: ChatMensagem = {
  role: 'assistant',
  content: 'Olá! Sou o assistente de DRE da MX Seguros. Posso ajudar com análises financeiras, comparativos de períodos, receita por ramo e muito mais. O que você gostaria de saber?',
}

export default function AssistentePage() {
  const { token } = useAuth()
  const [mensagens, setMensagens] = useState<ChatMensagem[]>([MSG_BOAS_VINDAS])
  const [input, setInput] = useState('')
  const [conversaId, setConversaId] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensagens])

  async function enviar() {
    if (!token || !input.trim() || streaming) return
    const texto = input.trim()
    setInput('')
    setErro(null)
    setMensagens((prev) => [...prev, { role: 'user', content: texto }])
    setStreaming(true)

    const params = new URLSearchParams({ mensagem: texto })
    if (conversaId) params.set('conversa_id', conversaId)

    let buffer = ''
    setMensagens((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      const res = await fetch(`${BASE}/chat/stream?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.body) throw new Error('Stream indisponível')
      const reader = res.body.getReader()
      const dec = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        for (const line of dec.decode(value, { stream: true }).split('\n')) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') continue
          try {
            const p = JSON.parse(payload)
            if (p.conversa_id) setConversaId(p.conversa_id)
            if (p.texto) {
              buffer += p.texto
              setMensagens((prev) => {
                const c = [...prev]
                c[c.length - 1] = { role: 'assistant', content: buffer }
                return c
              })
            }
          } catch { /* linha parcial */ }
        }
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Erro ao conectar com o chat')
      setMensagens((prev) => prev.slice(0, -1))
    } finally {
      setStreaming(false)
      inputRef.current?.focus()
    }
  }

  return (
    <div className="flex h-[calc(100dvh-9rem)] flex-col lg:h-[calc(100dvh-4rem)]">
      <div className="mb-3">
        <h1 className="text-xl font-bold text-[#071934] md:text-2xl">Assistente IA</h1>
        <p className="text-sm text-gray-500">Análises inteligentes do seu DRE — pergunte em português</p>
      </div>

      {/* Área de mensagens */}
      <div className="flex-1 overflow-y-auto rounded-2xl bg-white p-4 shadow-sm sm:p-6">
        <div className="space-y-5">
          {mensagens.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              {msg.role === 'assistant' ? <BotIcon /> : <UserIcon />}
              <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-[#071934] text-white'
                  : 'bg-gray-50 text-gray-800'
              }`}>
                {msg.content || (streaming && msg.role === 'assistant' ? (
                  <span className="flex gap-1">
                    <span className="animate-bounce">·</span>
                    <span className="animate-bounce" style={{ animationDelay: '0.1s' }}>·</span>
                    <span className="animate-bounce" style={{ animationDelay: '0.2s' }}>·</span>
                  </span>
                ) : '')}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {erro && <p className="mt-1 text-xs text-red-500">{erro}</p>}

      {/* Input */}
      <div className="mt-3 flex gap-2 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm">
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && enviar()}
          disabled={streaming}
          placeholder="Pergunte sobre o DRE... (Enter para enviar)"
          className="flex-1 bg-transparent text-sm text-gray-700 placeholder-gray-400 focus:outline-none disabled:opacity-60"
        />
        <button
          onClick={enviar}
          disabled={streaming || !input.trim()}
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#071934] text-white hover:bg-[#0E2444] disabled:opacity-40"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-4 w-4">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  )
}


