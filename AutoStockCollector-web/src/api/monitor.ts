import client from './client'

export interface MonitorSignal {
  code: string
  name: string
  type: string
  price: number
  change_rate: number
  industry: string
  confidence: number
  short_term: SignalDimension
  long_term: SignalDimension
  composite: {
    score: number
    signal: string
    label: string
    divergence: string
  }
  analysis: {
    fund_flow: any
    research: any
    technical: any
    fundamental: any
  }
  updated_at: string
}

export interface SignalDimension {
  score: number
  signal: string
  signal_label?: string
  breakdown?: Record<string, number>
  reasons: string[]
  weights?: Record<string, number>
}

export interface SignalHistoryPoint {
  code: string
  short_term: SignalDimension
  long_term: SignalDimension
  composite: { score: number; signal: string }
  price: number
  change_rate: number
  confidence: number
  created_at: string
}

export const monitorApi = {
  getSignals() {
    return client.get('/api/v1/monitor/signals')
  },
  getSignal(code: string) {
    return client.get(`/api/v1/monitor/signals/${encodeURIComponent(code)}`)
  },
  getSignalHistory(code: string, days = 30) {
    return client.get(`/api/v1/monitor/signals/${encodeURIComponent(code)}/history`, { params: { days } })
  },
  refresh() {
    return client.post('/api/v1/monitor/refresh')
  },
  refreshStock(code: string) {
    return client.post(`/api/v1/monitor/refresh/${encodeURIComponent(code)}`)
  },
  scan() {
    return client.get('/api/v1/monitor/scan')
  },
}
