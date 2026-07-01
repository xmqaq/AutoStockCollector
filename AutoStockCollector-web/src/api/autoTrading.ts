import client from './client'

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
}

export interface FusedSignalBreakdown {
  auction_score: number
  auction_gap: number
  auction_trap: boolean
  pa_signal: string
  pa_confidence: number
  ai_score: number
  ai_signal: string
  industry?: string
}

export interface FusedSignalItem {
  code: string
  name: string
  overall_score: number
  signal: string
  reasons: string[]
  held: boolean
  breakdown: FusedSignalBreakdown
}

export interface AutoTradePosition {
  code: string
  name: string
  shares: number
  avg_cost: number
  current_price: number
  market_value: number
  pnl: number
  pnl_percent: number
  stop_loss: number | null
  take_profit: number | null
  sl_hit?: boolean
  tp_hit?: boolean
}

export interface AutoTradeStats {
  last_cycle: string | null
  total_run: number
  buys: number
  sells: number
  adds: number
  reduces: number
  errors: number
  status: string
}

export interface AutoTradeStatus {
  enabled: boolean
  account_cash: number
  initial_capital: number
  total_market_value: number
  total_pnl: number
  total_pnl_pct: number
  position_count: number
  max_positions: number
  exposure_pct: number
  positions: AutoTradePosition[]
  stats: AutoTradeStats
}

export interface CycleResult {
  date: string
  cycle_time: string
  user_id?: string
  positions_checked: number
  candidates_checked: number
  buys: number
  sells: number
  adds: number
  reduces: number
  errors: number
  message?: string
  details: {
    action: string
    code: string
    name?: string
    shares: number
    price?: number
    stop_loss?: number | null
    take_profit?: number | null
    source?: string
    reason?: string
  }[]
}

export interface AutoTradeConfig {
  weights: {
    auction: number
    pa: number
    ai_monitor: number
  }
  thresholds: {
    buy: number
    add: number
    reduce: number
    sell: number
  }
  risk: {
    max_positions: number
    max_exposure_pct: number
    max_single_pct: number
    max_sector_pct: number
    exclude_st?: boolean
    exclude_new_listing_days?: number
    limit_up_block?: boolean
    limit_down_block?: boolean
  }
  sl_tp?: {
    sl_atr_multiplier: number
    tp_atr_multiplier: number
  }
  timing?: {
    scan_interval_minutes: number
    auto_close_time: string
  }
  auction_qual?: {
    min_auction_score: number
    min_auction_gap: number
  }
  cache?: {
    signal_cache_ttl_seconds: number
    fusion_workers: number
  }
  updated_at?: string
}

export interface DrawdownStrategyConfig {
  enabled: boolean
  trailing_stop_pct: number
  trailing_action: 'sell' | 'reduce'
  reduce_ratio: number
  profit_lock_enabled: boolean
  profit_lock_threshold: number
  max_drawdown_pct: number
  updated_at?: string
}

export const autoTradingApi = {
  getStatus() {
    return client.get<ApiResponse<AutoTradeStatus>>('/api/v1/auto-trading/status')
  },
  getSignals(date?: string) {
    return client.get<ApiResponse<{ date: string; signals: FusedSignalItem[]; count: number }>>(
      '/api/v1/auto-trading/signals',
      { params: { date } },
    )
  },
  triggerCycle(date?: string) {
    return client.post<ApiResponse<CycleResult>>('/api/v1/auto-trading/cycle', { date })
  },
  getConfig() {
    return client.get<ApiResponse<AutoTradeConfig>>('/api/v1/auto-trading/config')
  },
  saveConfig(cfg: Partial<AutoTradeConfig>) {
    return client.post<ApiResponse<AutoTradeConfig>>('/api/v1/auto-trading/config', cfg)
  },
  getHistory(limit = 50) {
    return client.get<ApiResponse<CycleResult[]>>('/api/v1/auto-trading/history', {
      params: { limit },
    })
  },
  closeAllPositions() {
    return client.post<ApiResponse<{ closed: number; total: number }>>('/api/v1/auto-trading/close-positions')
  },
  getDrawdownStrategy() {
    return client.get<ApiResponse<DrawdownStrategyConfig>>('/api/v1/auto-trading/drawdown-strategy')
  },
  saveDrawdownStrategy(cfg: DrawdownStrategyConfig) {
    return client.post<ApiResponse<DrawdownStrategyConfig>>('/api/v1/auto-trading/drawdown-strategy', cfg)
  },
}
