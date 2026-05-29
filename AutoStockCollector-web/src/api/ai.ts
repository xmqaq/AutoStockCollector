import client from './client'

export interface AIKeyConfig {
  provider: string
  name: string
  enabled: boolean
  priority: number
  has_key?: boolean
  updated_at?: string
  api_key?: string
  base_url?: string
}

export interface PickedStock {
  code: string
  total: number
  scores: Record<string, number>
}

export const aiKeyApi = {
  list() {
    return client.get('/api/v1/ai-keys')
  },
  update(data: Partial<AIKeyConfig> & { api_key?: string }) {
    return client.post('/api/v1/ai-keys', data)
  },
  remove(provider: string) {
    return client.delete(`/api/v1/ai-keys/${provider}`)
  },
  test(provider: string, apiKey?: string, baseUrl?: string) {
    return client.post(`/api/v1/ai-keys/${provider}/test`, { api_key: apiKey, base_url: baseUrl })
  },
  reorder(priorities: { provider: string; priority: number }[]) {
    return client.put('/api/v1/ai-keys/reorder', { priorities })
  },
}

export const pickerApi = {
  smartPick(topN = 10, factors = ['trend', 'volume', 'value', 'fund_flow']) {
    return client.post('/api/v1/pick/smart', { top_n: topN, factors })
  },
}

export const aiApi = {
  analyze(params: { code: string; type: string }) {
    return client.post('/api/v1/ai/analyze', params)
  },
  list() {
    return client.get('/api/v1/ai-keys')
  },
  analyzeStock(params: { code: string }) {
    return client.post('/api/v1/ai/analyze-stock', params)
  },
  analyzeNews(params: { news: Record<string, unknown> }) {
    return client.post('/api/v1/ai/analyze-news', params)
  },
}
