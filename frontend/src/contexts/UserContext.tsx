'use client'
import { createContext, useContext } from 'react'
import type { Role } from '@/types'

export interface UserContextValue {
  role: Role | null
  nome: string
  email: string
}

const UserContext = createContext<UserContextValue>({ role: null, nome: '', email: '' })

export function useUser() {
  return useContext(UserContext)
}

export { UserContext }
