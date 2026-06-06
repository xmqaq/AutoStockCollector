import client from './client'

export interface NewsParams {
  code?: string
  type?: string
  channel?: string
  breaking?: boolean
  limit?: number
  skip?: number
}

export interface NewsCategory {
  id: string
  name: string
  description: string
}

export interface NewsStats {
  total: number
  by_type: Record<string, number>
  by_channel: Record<string, number>
  breaking_count: number
}

export const newsApi = {
  getNews(params?: NewsParams) {
    return client.get('/api/v1/news', { params })
  },

  latest(params?: { code?: string; limit?: number }) {
    return client.get('/api/v1/news', { params })
  },

  getCategories() {
    return client.get('/api/v1/news/categories')
  },

  getStats() {
    return client.get('/api/v1/news/stats')
  },

  getBreaking(limit?: number) {
    return client.get('/api/v1/news/breaking', { params: { limit } })
  },

  collect(params?: { use_sina?: boolean; limit?: number }) {
    return client.post('/api/v1/collect/news', params)
  }
}
