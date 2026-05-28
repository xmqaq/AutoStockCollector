import client from './client'

export const strategyApi = {
  getStrategyList() {
    return client.get('/api/v1/strategy/list')
  },
}
