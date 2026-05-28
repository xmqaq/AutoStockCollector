import client from './client'

export const stockApi = {
  getStockInfo(code: string) {
    return client.get(`/api/v1/stock/${code}/info`)
  },
}
