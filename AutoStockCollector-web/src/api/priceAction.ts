import client from './client'

export interface PaTradePlan {
  direction: string
  entry: number
  stop_loss: number
  take_profit: number
  position_size: number
  position_value: number
  risk_per_share: number
  total_risk: number
  r_r_ratio: string
}

export interface PaSignal {
  symbol: string
  name?: string
  current_price: number
  signal: 'BUY_SETUP' | 'SELL_SETUP' | 'WEAK_BUY' | 'WEAK_SELL' | 'NEUTRAL' | 'NO_TRADE' | 'NO_DATA' | 'ERROR'
  confidence: number
  trend?: string
  reasons: string[]
  zones: any[]
  patterns: string[]
  fib_levels?: Record<string, number>
  atr: number
  sweeps_detected: number
  trade_plan?: PaTradePlan
  error?: string
  ai_commentary?: string
}

export const priceActionApi = {
  getSingle(symbol: string, timeframe = 'daily', risk = 0.02, balance = 100000, useAi = false) {
    return client.get<{ success: boolean; data: PaSignal }>('/api/v1/ai/price-action/single', {
      params: { symbol, timeframe, risk, balance, use_ai: useAi },
    })
  },
  run(symbols: string[], timeframe = 'daily', accountRisk = 0.02, accountBalance = 100000, useAi = false) {
    return client.post('/api/v1/ai/price-action', { symbols, timeframe, account_risk: accountRisk, account_balance: accountBalance, use_ai: useAi })
  },
  getResult(taskId: string) {
    return client.get(`/api/v1/ai/price-action/result/${taskId}`)
  },
  getHistory() {
    return client.get<{ success: boolean; count: number; data: any[] }>('/api/v1/ai/price-action/history')
  },
}
