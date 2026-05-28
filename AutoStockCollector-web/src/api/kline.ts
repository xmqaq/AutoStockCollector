import client from './client'

export const klineApi = {
  getKline(code: string, params?: { start_date?: string; end_date?: string }) {
    return client.get(`/api/v1/kline/${code}`, { params })
  },
}
