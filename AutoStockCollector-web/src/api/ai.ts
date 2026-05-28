import client from './client'

export const aiApi = {
  analyze(data: { code: string; type: string }) {
    return client.post('/api/v1/ai/analyze', data)
  },
}
