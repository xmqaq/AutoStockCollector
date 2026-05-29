import client from './client'

export interface StrategyConfig {
  name: string
  strategy_type: string
  description: string
  params: Record<string, number>
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export const strategyConfigApi = {
  getList(enabledOnly = false) {
    return client.get('/api/v1/strategy-configs', { params: { enabled_only: enabledOnly } })
  },

  get(name: string) {
    return client.get(`/api/v1/strategy-configs/${encodeURIComponent(name)}`)
  },

  create(data: Omit<StrategyConfig, 'created_at' | 'updated_at'>) {
    return client.post('/api/v1/strategy-configs', data)
  },

  update(name: string, params: Record<string, number>) {
    return client.put(`/api/v1/strategy-configs/${encodeURIComponent(name)}`, { params })
  },

  toggle(name: string, enabled: boolean) {
    return client.post(`/api/v1/strategy-configs/${encodeURIComponent(name)}/toggle`, { enabled })
  },

  delete(name: string) {
    return client.delete(`/api/v1/strategy-configs/${encodeURIComponent(name)}`)
  },
}