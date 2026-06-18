import client from './client'

export interface TradingAdvice {
  action: string
  action_signal: string
  signal_source?: string
  reason: string
  details: Record<string, number>
  buy_reasons?: string[]
  sell_reasons?: string[]
  watch_reasons?: string[]
  reasons?: string[]
  entry_price_range: { low: number; high: number }
  take_profit: number
  stop_loss: number
  expected_return: number
  max_loss: number
  risk_reward_ratio: number
  current_position: string
  distance_to_target: string
  advice: {
    summary: string
    buy_price_low: number
    buy_price_high: number
    target_price: number
    stop_loss_price: number
    hold_period: string
    expected_return: number
    max_loss: number
    time_horizon: string
    confidence_level: string
    entry_price: number
  }
  divergence_warnings?: string[]
  reflection?: {
    previous_action: string
    previous_price: number
    current_price: number
    change_pct: number
    summary: string
  }
}

export interface SectorFlow {
  industry_name?: string
  industry_change?: number
  industry_net_flow?: number
  industry_total_amount?: number
}

export interface LimitUpInfo {
  is_limit_up?: boolean
  is_limit_down?: boolean
  consecutive_limit_days?: number
  limit_type?: string | null
  change_pct?: number
  turnover_rate?: number
  volume_ratio?: number
  amount?: number
}

export interface DragonTigerInfo {
  appearances?: number
  total_net_buy?: number
  institution_net_buy?: number
  hot_unknown_net_buy?: number
  top_brokers?: string[]
}

export interface MarginInfo {
  margin_balance?: number
  margin_balance_change_pct?: number
  short_volume?: number
  short_change_pct?: number
  short_ratio?: number
  trend?: string
  short_trend?: string
}

export interface NewsSentiment {
  overall: {
    score: number
    signal: string
    bullish: boolean
  }
  news_count: number
  positive_count: number
  negative_count: number
  neutral_count: number
  recent_positive_news: { title: string; date: string; source: string; keywords: string[] }[]
  recent_negative_news: { title: string; date: string; source: string; keywords: string[] }[]
  keywords_found: { bullish: string[]; bearish: string[] }
  reasons: string[]
}

export interface PricePrediction {
  target_price: number
  stop_loss: number
  expected_return: number
  max_loss: number
  position_size: number
  risk_level: string
  buy_zone_low: number
  buy_zone_high: number
  support: number
  resistance: number
  volatility: number
}

export interface MonitorSignal {
  code: string
  name: string
  type: string
  price: number
  change_rate: number
  industry: string
  concepts?: string[]
  concept_details?: { name: string; change_pct: number; net_flow: number }[]
  sector_flow?: SectorFlow
  limit_up?: LimitUpInfo
  dragon_tiger?: DragonTigerInfo
  margin?: MarginInfo
  confidence: number
  short_term: SignalDimension
  long_term: SignalDimension
  composite: {
    score: number
    signal: string
    label: string
    divergence: string
  }
  price_prediction?: PricePrediction
  trading_advice?: TradingAdvice
  analysis: {
    fund_flow: any
    research: any
    technical: any
    fundamental: any
    valuation: any
    news_sentiment?: NewsSentiment
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
  getSectorSentiment() {
    return client.get('/api/v1/monitor/sector-sentiment')
  },
  getFundFlowAnomalies(days = 5, limit = 100) {
    return client.get('/api/v1/monitor/fund-flow-anomalies', { params: { days, limit } })
  },
  getConfig() {
    return client.get('/api/v1/monitor/config')
  },
  saveConfig(config: MonitorTrackConfig) {
    return client.put('/api/v1/monitor/config', config)
  },
  getPortfolio() {
    return client.get('/api/v1/monitor/portfolio')
  },
}

// ── 双轨道调仓监控 ──

export interface TrackWeights {
  fundamental: number
  technical: number
  fund_flow: number
  valuation: number
}

export interface LongTermConfig {
  roe_min: number
  revenue_growth_min: number
  pe_percentile_max: number
  max_positions: number
  fund_ratio: number
  weight_overrides: TrackWeights
  candidate_pool: number
}

export interface ShortTermConfig {
  main_net_inflow_min: number
  news_positive_min: number
  max_positions: number
  fund_ratio: number
  weight_overrides: TrackWeights
  candidate_pool: number
}

export interface MonitorTrackConfig {
  long_term: LongTermConfig
  short_term: ShortTermConfig
}

export interface TrackAdvice {
  code: string
  name: string
  track: string
  action: string
  reason: string
  buy_price_low: number
  buy_price_high: number
  target_price: number
  stop_loss: number
  suggested_amount: number
  composite_score: number
}

export interface PortfolioSummary {
  total_value: number
  cash: number
  position_value: number
  long_available: number
  short_available: number
  long_ratio: number
  short_ratio: number
  position_count: number
}

export interface AnomalyAlert {
  code: string
  name: string
  latest_date: string
  latest_net: number
  z_score: number
  consecutive_days: number
  reversal: boolean
  anomaly_score: number
  anomaly_type: string
  is_holding: boolean
}

export interface MonitorPortfolio {
  long_term_advice: TrackAdvice[]
  short_term_advice: TrackAdvice[]
  swap_out_advice: TrackAdvice[]
  portfolio_summary: PortfolioSummary
  anomaly_alerts: AnomalyAlert[]
  analyzed: number
  timestamp: string
}

export interface FundFlowAnomaly {
  code: string
  name: string
  latest_date: string
  latest_net: number
  latest_amount: number
  latest_price: number
  latest_change: number
  latest_turnover: number
  avg_net: number
  std_net: number
  z_score: number
  consecutive_days: number
  net_ratio: number
  reversal: boolean
  anomaly_score: number
  anomaly_type: string
  data_days: number
}
