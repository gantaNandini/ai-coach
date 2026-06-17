import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  roles: string[]
  setAuth: (user: User, accessToken: string, refreshToken: string) => void
  clearAuth: () => void
  setRoles: (roles: string[]) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      roles: [],
      setAuth: (user, accessToken, refreshToken) => {
        localStorage.setItem('access_token', accessToken)
        localStorage.setItem('refresh_token', refreshToken)
        // Extract roles from user object (populated by /auth/me)
        const roles = user.roles ?? []
        set({ user, accessToken, refreshToken, roles })
      },
      clearAuth: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, accessToken: null, refreshToken: null, roles: [] })
      },
      setRoles: (roles) => set({ roles }),
    }),
    { name: 'auth-storage' }
  )
)
