import client from './client'

export interface AICallRecord {
  provider: string
  task_type: string
  success: boolean
  error?: string
  timestamp: string
  model_name?: string
  prompt_tokens?: number
  completion_tokens?: number
  latency_ms?: number
}

export interface AICallStats {
  total: number
  by_provider: Record<string, number>
  by_task_type: Record<string, number>
  success: number
  fail: number
  today: number
}

export const aiCallHistoryApi = {
  list(params: {
    page?: number
    size?: number
    provider?: string
    task_type?: string
    success?: string
    keyword?: string
  } = {}) {
    return client.get('/api/v1/ai-call-history', { params })
  },
}
