import request from './client'

export interface PaperAccount {
  user_id: string
  initial_capital: number
  cash_balance: number
  frozen_cash?: number  // 买入挂单冻结的资金（仍属总资产，但不计入可用现金）
  created_at: string
  updated_at: string
}

export interface PaperPosition {
  code: string
  name: string
  shares: number
  available_shares?: number   // T+1 + 挂单冻结后可卖
  frozen_shares?: number      // 卖出挂单冻结
  today_buy_shares?: number   // 当日买入（T+1 锁定）
  avg_cost: number
  current_price: number
  market_value: number
  pnl: number
  pnl_percent: number
  today_pnl_percent: number
  today_pnl_amount: number
  yesterday_close: number | null
  price_type: 'realtime' | 'close' | 'fallback' | 'unknown'
  position_ratio: number
}

export interface PaperOrder {
  _id: string
  user_id: string
  code: string
  name: string | null
  action: 'buy' | 'sell'
  shares: number
  price: number | null
  status: 'pending' | 'filled' | 'cancelled'
  ai_signal?: AiSignal
  stop_loss?: number | null
  take_profit?: number | null
  created_at: string
  filled_at?: string | null
  filled_price?: number | null
  cancel_reason?: string | null
  frozen_cash?: number
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

/** 下单结果：即时成交返回 filled（含成交记录），非交易时段挂单返回 pending（含订单）。 */
export type TradeResult =
  | { status: 'filled'; trade: TradeRecord; order_id: string }
  | { status: 'pending'; order: PaperOrder; order_id: string }

export interface PaperStats {
  total_trades: number
  win_trades: number
  loss_trades: number
  win_rate: number
  avg_profit_pct: number
  avg_loss_pct: number
  profit_factor: number
  total_fee: number
}

export interface NavPoint {
  date: string
  cash: number
  nav?: number
  net_value?: number
  market_value?: number
  profit_amount?: number
  profit_pct?: number
  initial_capital?: number
}

export interface RankingEntry {
  rank: number
  user_id: string
  username: string
  raw_username?: string
  initial_capital: number
  cash_balance: number
  frozen_cash?: number
  market_value: number
  total_asset: number
  profit_pct: number
  profit_amount: number
  today_pnl: number
  total_fee: number
  win_rate: number
  total_trades: number
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

  async depositAccount(amount: number): Promise<PaperAccount> {
    const res = await request.post<{ data: PaperAccount }>('/api/paper/account/deposit', {
      amount,
    })
    return res.data.data
  },

  async getPositions(): Promise<{ positions: PaperPosition[]; is_trading_time: boolean }> {
    const res = await request.get<{ data: PaperPosition[]; is_trading_time: boolean }>('/api/paper/positions')
    return {
      positions: res.data?.data ?? [],
      is_trading_time: res.data?.is_trading_time ?? false,
    }
  },

  async getPrice(code: string): Promise<{ price: number; price_type: string; is_trading_time: boolean } | null> {
    try {
      const res = await request.get<{ data: { price: number; price_type: string; is_trading_time: boolean } }>(`/api/paper/price?code=${encodeURIComponent(code)}`)
      return res.data?.data ?? null
    } catch {
      return null
    }
  },

  async executeTrade(payload: {
    code: string
    action: 'buy' | 'sell'
    shares: number
    price?: number
    ai_signal?: AiSignal
  }): Promise<TradeResult> {
    const res = await request.post<{ data: TradeResult }>('/api/paper/trade', payload)
    return res.data.data
  },

  async getOrders(status: 'pending' | 'filled' | 'cancelled' | 'all' = 'all'): Promise<PaperOrder[]> {
    try {
      const res = await request.get<{ data: PaperOrder[] }>(`/api/paper/orders?status=${status}`)
      return res.data?.data ?? []
    } catch {
      return []
    }
  },

  async cancelOrder(orderId: string): Promise<PaperOrder> {
    const res = await request.post<{ data: PaperOrder }>('/api/paper/orders/cancel', { order_id: orderId })
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
      win_rate: 0, avg_profit_pct: 0, avg_loss_pct: 0, profit_factor: 0, total_fee: 0,
    }
  },

  async getNav(): Promise<NavPoint[]> {
    const res = await request.get<{ data: NavPoint[] }>('/api/paper/nav')
    return res.data?.data ?? []
  },

  async getPositionsByUser(userId: string): Promise<PaperPosition[]> {
    try {
      const res = await request.get<{ data: PaperPosition[] }>(`/api/paper/positions?user_id=${encodeURIComponent(userId)}`)
      return res.data?.data ?? []
    } catch {
      return []
    }
  },

  async getTradesByUser(userId: string, limit = 50): Promise<TradeRecord[]> {
    try {
      const res = await request.get<{ data: TradeRecord[] }>(`/api/paper/trades?user_id=${encodeURIComponent(userId)}&limit=${limit}`)
      return res.data?.data ?? []
    } catch {
      return []
    }
  },

  async getRanking(live = false, silent = false): Promise<RankingEntry[]> {
    try {
      const res = await request.get<{ data: RankingEntry[] }>(`/api/paper/ranking${live ? '?live=1' : ''}`, {
        skipErrorMessage: silent,
      } as any)
      return res.data?.data ?? []
    } catch {
      return []
    }
  },

  async getAiAdvice(code: string, cost?: number, position?: number): Promise<AiSignal> {
    const params = new URLSearchParams({ code })
    if (cost != null) params.set('cost', String(cost))
    if (position != null) params.set('position', String(position))
    const res = await request.get<{ advice: AiSignal }>(`/api/v1/advice?${params}`)
    return res.data?.advice ?? {}
  },
}
