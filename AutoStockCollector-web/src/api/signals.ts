import client from './client'

export interface Signal {
  signal_id: string
  publisher_id: string
  publisher_name: string
  type: 'trade_idea' | 'analysis' | 'alert' | 'risk'
  direction: 'bullish' | 'bearish' | 'neutral'
  target: { code: string; name?: string }
  price?: number
  confidence: number
  reasoning: string
  timestamp: string
  expiry?: string
  status: 'active' | 'expired' | 'executed' | 'cancelled'
}

export const signalApi = {
  publish(data: {
    publisher_id: string
    publisher_name?: string
    type: string
    direction: string
    target: { code: string; name?: string }
    price?: number
    confidence?: number
    reasoning?: string
  }) {
    return client.post('/api/v1/signals/publish', data)
  },
  getFeed(params?: { limit?: number; publisher_id?: string; direction?: string; type?: string }) {
    return client.get('/api/v1/signals/feed', { params })
  },
  getSignal(signalId: string) {
    return client.get(`/api/v1/signals/${signalId}`)
  },
  expire(signalId: string) {
    return client.post(`/api/v1/signals/${signalId}/expire`)
  },
}
