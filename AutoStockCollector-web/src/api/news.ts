import client from './client'

export const newsApi = {
  getNews(params?: { code?: string; limit?: number }) {
    return client.get('/api/v1/news', { params })
  },
}
