import client from './client'

export interface CollectHistoryParams {
  start_date: string
  end_date: string
  task_types?: string[]
}

export interface ClearDbParams {
  collections?: string[]
}

export const collectApi = {
  getHealth() {
    return client.get('/health')
  },

  getProgressAll() {
    return client.get('/api/v1/collect/progress_all')
  },

  collectHistory(params: CollectHistoryParams) {
    return client.post('/api/v1/collect/history', params)
  },

  clearDb(params: ClearDbParams = {}) {
    return client.post('/api/v1/db/clear', params)
  },

  getTasks(params?: { status?: string; limit?: number }) {
    return client.get('/api/v1/tasks', { params })
  },

  cancelTask(id: string) {
    return client.post(`/api/v1/task/${id}/cancel`)
  },

  retryTask(id: string) {
    return client.post(`/api/v1/task/${id}/retry`)
  },
}
