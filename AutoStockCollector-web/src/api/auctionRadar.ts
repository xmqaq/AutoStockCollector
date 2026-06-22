import client from './client'

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
}

export interface RadarStock {
  symbol: string
  name: string
  open_price: number
  gap_pct: number
  auction_amount: number
  strength_score: number
  strength_detail?: {
    score: number
    gap_score: number
    volume_score: number
    sector_score: number
    deviation_score: number
  }
  trap_warning?: {
    is_trap: boolean
    trap_type: string
    reason: string
  }
  sector_rank: number
  industry: string
  highlight: boolean
  highlight_reason: string
}

export interface RadarResult {
  date: string
  scan_time: string
  status: string
  total_scanned: number
  top_stocks: RadarStock[]
  sector_leaders: { sector: string; leader: string; name: string; score: string }[]
  trap_warnings: { symbol: string; name: string; trap_type: string; reason: string; strength_score: number }[]
  summary: string
  created_at: string
}

export interface PositionSuggestion {
  symbol: string
  name: string
  action: 'buy' | 'observe' | 'skip'
  position_pct: number
  confidence: 'low' | 'medium' | 'high'
  reason: string
}

export interface PositionResult {
  total_used_pct: number
  buy_count: number
  suggestions: PositionSuggestion[]
  summary: string
}

export interface PerformanceBucket {
  score_bracket: string
  count: number
  wins: number
  avg_return: number
  total_return: number
}

export interface PerformanceStats {
  buckets: PerformanceBucket[]
  days: number
}

export interface PerformanceRecord {
  code: string
  name: string
  date: string
  strength_score: number
  gap_pct: number
  industry: string
  is_trap: boolean
  trap_type: string
  result: string
  return_pct: number | null
  exit_reason: string
  created_at: string
}

export interface RiskPosition {
  code: string
  name: string
  shares: number
  avg_cost: number
  current_price: number
  market_value: number
  pnl: number
  pnl_percent: number
  today_pnl_percent: number
  stop_loss: number | null
  take_profit: number | null
  distance_to_sl: number | null
}

export interface RiskSummary {
  cash_balance: number
  total_market_value: number
  total_cost: number
  total_pnl: number
  total_pnl_pct: number
  position_count: number
  auto_trade_count: number
  max_positions: number
  total_exposure_pct: number
  max_exposure_pct: number
  sector_exposure: Record<string, number>
  positions: RiskPosition[]
  error?: string
}

export interface IntradayRecord {
  code: string
  name: string
  date: string
  open_price: number
  gap_pct: number
  strength_score: number
  industry: string
  is_trap: boolean
  trap_type: string
  status: string
  auto_trade_id: string
  current_price: number
  current_pnl_pct: number
  highest_pnl_pct: number
  lowest_pnl_pct: number
  updated_at: string
}

export const auctionRadarApi = {
  getStatus() {
    return client.get<ApiResponse<{ status: string; scan_time: string; date: string }>>(
      '/api/v1/ai/pre-market-radar/status',
    )
  },
  getResults() {
    return client.get<ApiResponse<RadarResult>>(
      '/api/v1/ai/pre-market-radar/results',
    )
  },
  triggerScan(symbols?: string[]) {
    return client.post<ApiResponse<RadarResult>>(
      '/api/v1/ai/pre-market-radar/trigger',
      { symbols },
    )
  },
  getPositionSuggestions() {
    return client.get<ApiResponse<PositionResult>>(
      '/api/v1/ai/pre-market-radar/position-suggestions',
    )
  },
  getPerformance(days = 30, minScore = 0) {
    return client.get<ApiResponse<PerformanceStats>>(
      '/api/v1/ai/pre-market-radar/performance',
      { params: { days, min_score: minScore } },
    )
  },
  getPerformanceHistory(days = 7, limit = 50) {
    return client.get<ApiResponse<{ records: PerformanceRecord[]; count: number }>>(
      '/api/v1/ai/pre-market-radar/performance/history',
      { params: { days, limit } },
    )
  },
  getIntradayData(date?: string, refresh = true) {
    return client.get<ApiResponse<{ records: IntradayRecord[]; count: number }>>(
      '/api/v1/ai/pre-market-radar/intraday',
      { params: { date, refresh: refresh ? '1' : '0' } },
    )
  },
  getRiskSummary() {
    return client.get<ApiResponse<RiskSummary>>(
      '/api/v1/ai/pre-market-radar/risk',
    )
  },
  triggerAutoClose() {
    return client.post<ApiResponse<{ closed: number }>>(
      '/api/v1/ai/pre-market-radar/auto-close',
    )
  },
}
