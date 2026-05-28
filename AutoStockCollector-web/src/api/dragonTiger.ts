import client from './client'

export const dragonTigerApi = {
  getDragonTiger(params?: { start_date?: string; end_date?: string; code?: string; limit?: number }) {
    return client.get('/api/v1/dragon_tiger', { params })
  },
}
