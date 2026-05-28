import client from './client'

export const financialApi = {
  getFinancial(code: string, params?: { report_date?: string }) {
    return client.get(`/api/v1/financial/${code}`, { params })
  },
}
