const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail ?? body?.erro ?? `HTTP ${res.status}`)
  }
  if (res.status === 204 || res.headers.get('content-length') === '0') {
    return undefined as unknown as T
  }
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string, token: string) => request<T>(path, token),
  post: <T>(path: string, token: string, body: unknown) =>
    request<T>(path, token, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, token: string, body: unknown) =>
    request<T>(path, token, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path: string, token: string, body: unknown) =>
    request<T>(path, token, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string, token: string) => request<T>(path, token, { method: 'DELETE' }),
}

export function streamChat(
  token: string,
  mensagem: string,
  conversaId: string | null,
  onChunk: (text: string) => void,
  onDone: (conversaId: string) => void,
  onError: (err: string) => void,
) {
  const params = new URLSearchParams({ mensagem })
  if (conversaId) params.set('conversa_id', conversaId)

  const es = new EventSource(`${BASE}/chat/stream?${params}`, {
    // EventSource não suporta headers diretamente; usamos query param como fallback
  })

  // Workaround: chat endpoint aceita token via query
  const url = `${BASE}/chat/stream?${params}&token=${token}`
  const esAuth = new EventSource(url)

  esAuth.onmessage = (e) => {
    if (e.data === '[DONE]') {
      esAuth.close()
      es.close()
      return
    }
    try {
      const parsed = JSON.parse(e.data)
      if (parsed.conversa_id) onDone(parsed.conversa_id)
      else if (parsed.texto) onChunk(parsed.texto)
    } catch {
      onChunk(e.data)
    }
  }
  esAuth.onerror = () => {
    esAuth.close()
    es.close()
    onError('Conexão com o chat perdida. Tente novamente.')
  }

  return () => { esAuth.close(); es.close() }
}
