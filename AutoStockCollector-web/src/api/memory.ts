import client from './client'

export interface UserProfile {
  user_id: string
  risk_level: string
  preferred_industries: string[]
  preferred_strategies: string[]
  holding_horizon: string
}

export interface HoldingRecord {
  code: string
  stock_name: string
  buy_date: string
  buy_price: number
  shares: number
  reason?: string
}

export interface AnalysisRecord {
  id: string
  code: string
  stock_name?: string
  analysis_type: string
  result?: string
  score?: number
  created_at: string
}

export interface InvestmentPattern {
  id: string
  pattern_type: string
  description: string
  confidence: number
  frequency: number
  created_at: string
}

export interface MemoryStats {
  analysis_count: number
  pattern_count: number
  holding_count: number
  last_active: string
  memory_rings: {
    name: string
    label: string
    item_count: number
  }[]
}

export const memoryApi = {
  getProfile(userId = 'default') {
    return client.get('/api/v1/memory/profile', { params: { user_id: userId } })
  },
  updateProfile(data: Partial<UserProfile>) {
    return client.put('/api/v1/memory/profile', data)
  },
  getHoldings(userId = 'default') {
    return client.get('/api/v1/memory/holdings', { params: { user_id: userId } })
  },
  addHolding(data: HoldingRecord & { user_id?: string }) {
    return client.post('/api/v1/memory/holdings', data)
  },
  getAnalyses(code?: string, userId = 'default') {
    return client.get('/api/v1/memory/analyses', { params: { code, user_id: userId } })
  },
  recordFeedback(analysisId: string, feedback: string, userId = 'default') {
    return client.post('/api/v1/memory/analyses/feedback', {
      user_id: userId,
      analysis_id: analysisId,
      feedback,
    })
  },
  getPatterns(userId = 'default') {
    return client.get('/api/v1/memory/patterns', { params: { user_id: userId } })
  },
  analyzePatterns(userId = 'default') {
    return client.post('/api/v1/memory/patterns/analyze', { user_id: userId })
  },
  getContext(code?: string, userId = 'default') {
    return client.get('/api/v1/memory/context', { params: { code, user_id: userId } })
  },
  getStats(userId = 'default') {
    return client.get('/api/v1/memory/stats', { params: { user_id: userId } })
  },
  clearSession(userId = 'default') {
    return client.post('/api/v1/memory/session/clear', { user_id: userId })
  },
}
