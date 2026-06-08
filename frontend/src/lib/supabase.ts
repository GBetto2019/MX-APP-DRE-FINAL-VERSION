import { createBrowserClient } from '@supabase/ssr'

// Strip BOM (U+FEFF) that can appear when env vars are copied from UTF-8-BOM encoded files
const stripBom = (s: string) => s.charCodeAt(0) === 0xfeff ? s.slice(1) : s

export function createClient() {
  const url = stripBom(process.env.NEXT_PUBLIC_SUPABASE_URL ?? '')
  const key = stripBom(process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? '')
  return createBrowserClient(url, key)
}
