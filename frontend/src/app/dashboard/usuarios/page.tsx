'use client'
import { useEffect, useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useUser } from '@/contexts/UserContext'
import { api } from '@/lib/api'
import { Skeleton } from '@/components/ui/Skeleton'
import { Badge } from '@/components/ui/Badge'
import type { UsuarioItem, Role } from '@/types'

const ROLE_VARIANT: Record<Role, 'info' | 'warning' | 'success' | 'default'> = {
  admin:     'danger' as 'info',
  gestor:    'warning',
  comercial: 'default',
  contador:  'info',
}

export default function UsuariosPage() {
  const { token } = useAuth()
  const { role: myRole } = useUser()
  const isAdmin = myRole === 'admin'
  const [usuarios, setUsuarios] = useState<UsuarioItem[]>([])
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [novoEmail, setNovoEmail] = useState('')
  const [novoNome, setNovoNome] = useState('')
  const [novoRole, setNovoRole] = useState<Role>('comercial')
  const [novaSenha, setNovaSenha] = useState('')
  const [criando, setCriando] = useState(false)

  function carregar() {
    if (!token) return
    api.get<{ total: number; items: UsuarioItem[] }>('/usuarios', token)
      .then((r) => setUsuarios(r.items))
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { carregar() }, [token]) // eslint-disable-line

  async function toggleAtivo(u: UsuarioItem) {
    if (!token) return
    await api.patch(`/usuarios/${u.id}`, token, { ativo: !u.ativo })
    carregar()
  }

  async function criarUsuario(e: React.FormEvent) {
    e.preventDefault()
    if (!token) return
    setCriando(true)
    try {
      await api.post('/usuarios', token, {
        nome: novoNome, email: novoEmail, senha: novaSenha, role: novoRole,
      })
      setNovoNome(''); setNovoEmail(''); setNovaSenha(''); setNovoRole('comercial')
      carregar()
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Erro ao criar usuário')
    } finally {
      setCriando(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-mx-navy">Gestão de Usuários</h1>

      <form onSubmit={criarUsuario}
        className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 font-semibold text-gray-800">Novo Usuário</h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <input required value={novoNome} onChange={(e) => setNovoNome(e.target.value)}
            placeholder="Nome" className="rounded border border-gray-300 px-3 py-2 text-sm focus:border-mx-blue focus:outline-none" />
          <input required type="email" value={novoEmail} onChange={(e) => setNovoEmail(e.target.value)}
            placeholder="E-mail" className="rounded border border-gray-300 px-3 py-2 text-sm focus:border-mx-blue focus:outline-none" />
          <input required type="password" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)}
            placeholder="Senha" className="rounded border border-gray-300 px-3 py-2 text-sm focus:border-mx-blue focus:outline-none" />
          <select value={novoRole} onChange={(e) => setNovoRole(e.target.value as Role)}
            className="rounded border border-gray-300 px-3 py-2 text-sm focus:border-mx-blue focus:outline-none">
            <option value="comercial">Comercial</option>
            <option value="gestor">Gestor</option>
            <option value="contador">Contador</option>
            {isAdmin && <option value="admin">Admin</option>}
          </select>
        </div>
        {erro && <p className="mt-2 text-sm text-red-600">{erro}</p>}
        <button type="submit" disabled={criando}
          className="mt-3 rounded-lg bg-mx-navy px-5 py-2 text-sm font-medium text-white hover:bg-mx-blue disabled:opacity-50">
          {criando ? 'Criando…' : 'Criar Usuário'}
        </button>
      </form>

      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-5"><Skeleton variant="table" /></div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left">
                <th className="px-5 py-3 font-medium text-gray-600">Nome</th>
                <th className="px-5 py-3 font-medium text-gray-600">E-mail</th>
                <th className="px-5 py-3 font-medium text-gray-600">Perfil</th>
                <th className="px-5 py-3 font-medium text-gray-600">Status</th>
                <th className="px-5 py-3 font-medium text-gray-600">Ações</th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id} className="border-t border-gray-50 hover:bg-gray-50">
                  <td className="px-5 py-3 font-medium">{u.nome}</td>
                  <td className="px-5 py-3 text-gray-500">{u.email}</td>
                  <td className="px-5 py-3">
                    <Badge variant={ROLE_VARIANT[u.role] ?? 'default'}>{u.role}</Badge>
                  </td>
                  <td className="px-5 py-3">
                    <Badge variant={u.ativo ? 'success' : 'default'}>
                      {u.ativo ? 'Ativo' : 'Inativo'}
                    </Badge>
                  </td>
                  <td className="px-5 py-3">
                    {isAdmin ? (
                      <button onClick={() => toggleAtivo(u)}
                        className="text-xs text-mx-blue hover:underline">
                        {u.ativo ? 'Desativar' : 'Ativar'}
                      </button>
                    ) : (
                      <span className="text-xs text-gray-300">—</span>
                    )}
                  </td>
                </tr>
              ))}
              {usuarios.length === 0 && (
                <tr><td colSpan={5} className="px-5 py-8 text-center text-gray-400">Nenhum usuário encontrado</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}


