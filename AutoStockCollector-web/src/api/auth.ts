import client from './client'

export interface LoginParams {
  username: string
  password: string
}

export interface RegisterParams {
  username: string
  password: string
  email?: string
}

export interface UserInfo {
  user_id: string
  username: string
  nickname?: string
  email: string
  role: string
  created_at?: string
}

export interface AuthResponse {
  token: string
  user: UserInfo
}

export const authApi = {
  login(params: LoginParams) {
    return client.post('/api/v1/auth/login', params)
  },

  register(params: RegisterParams) {
    return client.post('/api/v1/auth/register', params)
  },

  getProfile() {
    return client.get('/api/v1/auth/me')
  },

  updateProfile(data: Record<string, unknown>) {
    return client.put('/api/v1/auth/me', data)
  },

  // Admin endpoints
  getUsers() {
    return client.get('/api/v1/auth/users')
  },

  updateUserRole(userId: string, role: string) {
    return client.put(`/api/v1/auth/users/${userId}/role`, { role })
  },

  deleteUser(userId: string) {
    return client.delete(`/api/v1/auth/users/${userId}`)
  },
}
