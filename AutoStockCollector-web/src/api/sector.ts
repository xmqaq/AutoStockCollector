import client from './client'

export const sectorApi = {
  getSectors() {
    return client.get('/api/v1/sector')
  },

  getSectorStocks(name: string) {
    return client.get(`/api/v1/sector/${encodeURIComponent(name)}/stocks`)
  },
}
