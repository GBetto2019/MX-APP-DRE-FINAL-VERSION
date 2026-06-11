'use client'
import { createContext, useContext } from 'react'
import type { Role, Permissions } from '@/types'

export interface UserContextValue {
  role: Role | null
  nome: string
  email: string
  permissions: Permissions | null
}

const UserContext = createContext<UserContextValue>({ role: null, nome: '', email: '', permissions: null })

export function useUser() {
  return useContext(UserContext)
}

export { UserContext }
