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

export interface PaBacktest {
  total_trades: number
  win_rate: number
  avg_r: number
  profit_factor: number
  max_drawdown_pct: number
  sharpe_ratio: number
  max_consecutive_losses: number
  expectancy: number
  message?: string
}

export interface PaKlineBar {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface PaSignal {
  symbol: string
  name?: string
  industry?: string
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
  backtest?: PaBacktest
  error?: string
  ai_commentary?: string
  kline_bars?: PaKlineBar[]
}

export const priceActionApi = {
  getSingle(symbol: string, timeframe = 'daily', risk = 0.02, balance = 100000, useAi = false) {
    return client.post<{ success: boolean; task_id: string }>('/api/v1/ai/price-action/single', {
      symbol, timeframe, risk, balance, use_ai: useAi,
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
  getLatestScan() {
    return client.get<{ success: boolean; data: any }>('/api/v1/ai/price-action/scan/latest')
  },
  scan(symbols?: string[], timeframe = 'daily', accountRisk = 0.02, accountBalance = 100000) {
    const body: Record<string, any> = { timeframe, account_risk: accountRisk, account_balance: accountBalance }
    if (symbols) body.symbols = symbols
    return client.post('/api/v1/ai/price-action/scan', body)
  },
  async executeTrade(code: string, shares: number, price?: number, stopLoss?: number, takeProfit?: number) {
    return client.post('/api/paper/trade', {
      code,
      action: 'buy',
      shares,
      price: price || undefined,
      stop_loss: stopLoss,
      take_profit: takeProfit,
    })
  },
  getSignalHistory(code: string, days = 60) {
    return client.get<{ success: boolean; count: number; data: any[]; latest: any }>(
      `/api/v1/ai/price-action/signal-history/${encodeURIComponent(code)}`,
      { params: { days } },
    )
  },
  getSignalHistoryCodes(signal?: string, days = 7) {
    return client.get<{ success: boolean; count: number; data: any[] }>(
      '/api/v1/ai/price-action/signal-history/codes',
      { params: { signal, days } },
    )
  },
  getScanStatus() {
    return client.get<{ success: boolean; running: any; latest: any }>('/api/v1/ai/price-action/scan/status')
  },
}
