import client from './client'

export const factorApi = {
  list() {
    return client.get('/api/v1/workflow/factors/list')
  },
  updateWeights(weights: Record<string, number>) {
    return client.put('/api/v1/workflow/factors/weights', { weights })
  },
  resetWeights() {
    return client.post('/api/v1/workflow/factors/weights/reset')
  },
  icTestStart(daysAgo: number, periods: number[]) {
    return client.post('/api/v1/workflow/factors/ic-test/start', {
      days_ago: daysAgo,
      periods,
    })
  },
  icTestProgress(taskId: string) {
    return client.get(`/api/v1/workflow/factors/ic-test/progress/${taskId}`)
  },
  icTest(daysAgo: number, periods: number[]) {
    return client.post('/api/v1/workflow/factors/ic-test', {
      days_ago: daysAgo,
      periods,
    })
  },
  cacheStatus() {
    return client.get('/api/v1/workflow/factors/status')
  },
  triggerCacheUpdate() {
    return client.post('/api/v1/workflow/factors/update')
  },
  score(params: { days_back?: number; limit?: number; min_score?: number; weights?: Record<string, number> }) {
    return client.post('/api/v1/workflow/factors/score', params)
  },
  scoreStart(params: { days_back?: number; limit?: number; min_score?: number; weights?: Record<string, number> }) {
    return client.post('/api/v1/workflow/factors/score/start', params)
  },
  scoreProgress(taskId: string) {
    return client.get(`/api/v1/workflow/factors/score/progress/${taskId}`)
  },
  scoreCancel(taskId: string) {
    return client.post(`/api/v1/workflow/factors/score/cancel/${taskId}`)
  },
  correlation(params: { days_back?: number }) {
    return client.post('/api/v1/workflow/factors/correlation', params)
  },
  correlationStart(params: { days_back?: number }) {
    return client.post('/api/v1/workflow/factors/correlation/start', params)
  },
  correlationProgress(taskId: string) {
    return client.get(`/api/v1/workflow/factors/correlation/progress/${taskId}`)
  },
  correlationCancel(taskId: string) {
    return client.post(`/api/v1/workflow/factors/correlation/cancel/${taskId}`)
  },
  icTestCancel(taskId: string) {
    return client.post(`/api/v1/workflow/factors/ic-test/cancel/${taskId}`)
  },
  effectiveness(params: { days_back?: number }) {
    return client.post('/api/v1/workflow/factors/effectiveness', params)
  },
  weightPresets(params: { days_back?: number }) {
    return client.post('/api/v1/workflow/factors/weights/presets', params)
  },
}
