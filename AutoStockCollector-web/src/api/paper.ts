import request from './client'

export interface PaperAccount {
  user_id: string
  initial_capital: number
  cash_balance: number
  created_at: string
  updated_at: string
}

export interface PaperPosition {
  code: string
  name: string
  shares: number
  avg_cost: number
  current_price: number
  market_value: number
  pnl: number
  pnl_percent: number
  position_ratio: number
}

export interface TradeRecord {
  user_id: string
  code: string
  name: string
  action: 'buy' | 'sell'
  shares: number
  price: number
  amount: number
  commission: number
  ai_signal: {
    action?: string
    reason?: string
    composite?: number
  }
  cash_before: number
  cash_after: number
  traded_at: string
}

export interface PaperStats {
  total_trades: number
  win_trades: number
  loss_trades: number
  win_rate: number
  avg_profit_pct: number
  avg_loss_pct: number
  profit_factor: number
}

export interface NavPoint {
  date: string
  cash: number
  nav: number
}

export interface AiSignal {
  action?: string
  reason?: string
  composite?: number
  buy_zone?: string
  stop_loss?: string
  position_advice?: string
}

export const paperApi = {
  async getAccount(): Promise<PaperAccount | null> {
    try {
      const res = await request.get<{ data: PaperAccount }>('/api/paper/account')
      return res.data?.data ?? null
    } catch {
      return null
    }
  },

  async initAccount(initialCapital: number): Promise<PaperAccount> {
    const res = await request.post<{ data: PaperAccount }>('/api/paper/account/init', {
      initial_capital: initialCapital,
    })
    return res.data.data
  },

  async getPositions(): Promise<PaperPosition[]> {
    const res = await request.get<{ data: PaperPosition[] }>('/api/paper/positions')
    return res.data?.data ?? []
  },

  async executeTrade(payload: {
    code: string
    action: 'buy' | 'sell'
    shares: number
    ai_signal?: AiSignal
  }): Promise<TradeRecord> {
    const res = await request.post<{ data: TradeRecord }>('/api/paper/trade', payload)
    return res.data.data
  },

  async getTrades(limit = 10): Promise<TradeRecord[]> {
    const res = await request.get<{ data: TradeRecord[] }>(`/api/paper/trades?limit=${limit}`)
    return res.data?.data ?? []
  },

  async getStats(): Promise<PaperStats> {
    const res = await request.get<{ data: PaperStats }>('/api/paper/stats')
    return res.data?.data ?? {
      total_trades: 0, win_trades: 0, loss_trades: 0,
      win_rate: 0, avg_profit_pct: 0, avg_loss_pct: 0, profit_factor: 0,
    }
  },

  async getNav(): Promise<NavPoint[]> {
    const res = await request.get<{ data: NavPoint[] }>('/api/paper/nav')
    return res.data?.data ?? []
  },

  async getAiAdvice(code: string, cost?: number, position?: number): Promise<AiSignal> {
    const params = new URLSearchParams({ code })
    if (cost != null) params.set('cost', String(cost))
    if (position != null) params.set('position', String(position))
    const res = await request.get<{ advice: AiSignal }>(`/api/v1/advice?${params}`)
    return res.data?.advice ?? {}
  },
}
