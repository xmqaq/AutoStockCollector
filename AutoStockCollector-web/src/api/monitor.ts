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
  /** LLM 预测建议（与规则 advice 并列，由 /signals/<code>/ai-advice 或 cron 写入） */
  ai_advice?: AiAdvice
}

export interface AiAdvice {
  action: string
  confidence: number
  target_price: number
  stop_loss: number
  reason: string
  predicted_at?: string
  code?: string
}

export interface RealtimeQuote {
  code: string
  price: number
  change_rate: number
  volume_ratio: number
  turnover: number
  main_net_inflow: number
  main_inflow?: number
  main_outflow?: number
  total_amount?: number
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

export interface ExternalPaSignal {
  signal: string
  confidence: number
  trade_plan?: any
  scanned_at: string
  timeframe: string
}

export interface ExternalAuctionSignal {
  score: number
  gap_pct: number
  trap: boolean
  name?: string
  industry?: string
  date: string
}

export interface ExternalAgentSignal {
  score: number
  signal: string
  trade_date: string
  tendency?: string
}

export interface ExternalSignals {
  pa?: ExternalPaSignal | null
  auction?: ExternalAuctionSignal | null
  agent?: ExternalAgentSignal | null
  fusion_score?: number
  fusion_breakdown?: Record<string, number>
  fusion_weights?: Record<string, number>
}

export interface MonitorSignal {
  code: string
  name: string
  type: string
  price: number
  change_rate: number
  industry: string
  sources?: MonitorSource[]
  consecutive_days?: number
  strong_signal?: boolean
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
  /** 三路外部信号(PA/竞价/agent) + 综合融合分 */
  external_signals?: ExternalSignals
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
  getRealtime() {
    return client.get('/api/v1/monitor/realtime')
  },
  getAiAdvice(code: string, force = false) {
    return client.post(`/api/v1/monitor/signals/${encodeURIComponent(code)}/ai-advice${force ? '?force=1' : ''}`)
  },
  getPortfolio() {
    return client.get('/api/v1/monitor/portfolio')
  },
  getLifecycleStatus() {
    return client.get('/api/v1/monitor/lifecycle-status')
  },
  getFusionDetail(code: string) {
    return client.get(`/api/v1/monitor/signals/${encodeURIComponent(code)}/fusion-detail`)
  },
}

// ── 监控调仓（四来源：持仓 / 自选股 / AI智选 / 投研分析）──

export type MonitorSource = 'position' | 'watchlist' | 'fusion_pick' | 'research'

// 组合建议单项 = 身份 + 生命周期字段 + 现有 trading_advice 全部字段
export interface MonitorAdvice extends TradingAdvice {
  code: string
  name: string
  price: number
  sources: MonitorSource[]
  consecutive_days: number   // 仅 fusion_pick 来源有意义，否则为 0
  strong_signal: boolean     // consecutive_days >= 3
  first_selected_at: string  // 仅 fusion_pick 来源有值
}

export interface PortfolioSummary {
  total_value: number
  cash: number
  position_value: number
  monitor_count: number
  position_count: number
  watchlist_count: number
  fusion_pick_count: number
  overlap_count: number
  all_three_count: number
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
  in_monitor?: boolean
  monitor_sources?: MonitorSource[]
}

export interface MonitorPortfolio {
  advice: MonitorAdvice[]
  portfolio_summary: PortfolioSummary
  anomaly_alerts: AnomalyAlert[]
  lifecycle_summary?: Record<string, any>
  analyzed: number
  timestamp: string
}

export interface LifecycleStatus {
  total: number
  by_source: Record<MonitorSource, number>
  overlap: {
    position_and_watchlist: number
    position_and_fusion: number
    watchlist_and_fusion: number
    all_three: number
  }
  strong_signal_count: number
}

export interface FundFlowAnomaly {
  code: string
  name: string
  latest_date: string
  latest_net: number
  latest_amount?: number
  latest_price?: number
  latest_change?: number
  latest_turnover?: number
  avg_net?: number
  std_net?: number
  z_score: number
  consecutive_days: number
  net_ratio?: number
  reversal: boolean
  anomaly_score: number
  anomaly_type: string
  data_days?: number
  is_holding?: boolean
  in_monitor?: boolean
  monitor_sources?: string[]
}
