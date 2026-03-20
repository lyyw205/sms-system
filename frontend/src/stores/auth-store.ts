import { create } from 'zustand'

export interface AuthUser {
  id: number
  username: string
  name: string
  role: 'superadmin' | 'admin' | 'staff'
  active: boolean
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: AuthUser | null
  isAuthenticated: boolean
  login: (token: string, refreshToken: string, user: AuthUser) => void
  logout: () => void
  loadFromStorage: () => void
}

function getInitialAuth() {
  const token = localStorage.getItem('sms-token')
  const refreshToken = localStorage.getItem('sms-refresh-token')
  const userStr = localStorage.getItem('sms-user')
  if (token && userStr) {
    try {
      const user = JSON.parse(userStr) as AuthUser
      return { token, refreshToken, user, isAuthenticated: true }
    } catch {
      // invalid data
    }
  }
  return { token: null, refreshToken: null, user: null, isAuthenticated: false }
}

const initial = getInitialAuth()

export const useAuthStore = create<AuthState>((set) => ({
  token: initial.token,
  refreshToken: initial.refreshToken,
  user: initial.user,
  isAuthenticated: initial.isAuthenticated,

  login: (token, refreshToken, user) => {
    localStorage.setItem('sms-token', token)
    localStorage.setItem('sms-refresh-token', refreshToken)
    localStorage.setItem('sms-user', JSON.stringify(user))
    set({ token, refreshToken, user, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('sms-token')
    localStorage.removeItem('sms-refresh-token')
    localStorage.removeItem('sms-user')
    set({ token: null, refreshToken: null, user: null, isAuthenticated: false })
  },

  loadFromStorage: () => {
    const token = localStorage.getItem('sms-token')
    const refreshToken = localStorage.getItem('sms-refresh-token')
    const userStr = localStorage.getItem('sms-user')
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr) as AuthUser
        set({ token, refreshToken, user, isAuthenticated: true })
      } catch {
        localStorage.removeItem('sms-token')
        localStorage.removeItem('sms-refresh-token')
        localStorage.removeItem('sms-user')
      }
    }
  },
}))
