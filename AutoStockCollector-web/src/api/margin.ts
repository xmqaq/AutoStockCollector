import client from './client'

export const marginApi = {
  getMargin(params?: { start_date?: string; end_date?: string; code?: string; limit?: number }) {
    return client.get('/api/v1/margin', { params })
  },
}
