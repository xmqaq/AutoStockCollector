import client from './client'

export interface UserProfile {
  user_id: string
  risk_level: string
  preferred_industries: string[]
  preferred_strategies: string[]
  holding_horizon: string
}

export const memoryApi = {
  getProfile(userId = 'default') {
    return client.get('/api/v1/memory/profile', { params: { user_id: userId } })
  },
  updateProfile(data: Partial<UserProfile>) {
    return client.put('/api/v1/memory/profile', data)
  },
}
