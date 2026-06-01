import client from './client'

export const fundFlowApi = {
  getFundFlow(code: string) {
    return client.get(`/api/v1/fund-flow/${code}`)
  },

  getRank(params?: { limit?: number; date?: string }) {
    return client.get('/api/v1/fund-flow/rank', { params })
  },
}
