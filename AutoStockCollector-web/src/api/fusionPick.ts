import client from './client'

export const fusionPickApi = {
  /** 启动 AI 智选 */
  run(payload: {
    top_n?: number
    candidate_pool?: number
    strategy_ids?: string[]
    philosophy_ids?: string[]
    weight_overrides?: Record<string, number> | null
    filter_overrides?: Record<string, any> | null
  }) {
    return client.post<{ success: boolean; message?: string; error?: string }>(
      '/api/v1/fusion-pick/run', payload,
    )
  },

  /** 查询进度 */
  getProgress() {
    return client.get<{ success: boolean; data: FusionPickProgress }>('/api/v1/fusion-pick/progress')
  },

  /** 获取结果（可指定 run_id 获取历史） */
  getResult(runId?: string) {
    const params = runId ? { run_id: runId } : {}
    return client.get<{ success: boolean; data: FusionPickResult }>('/api/v1/fusion-pick/result', { params })
  },

  /** 历史结果摘要列表 */
  getHistory() {
    return client.get<{ success: boolean; data: FusionHistoryItem[] }>('/api/v1/fusion-pick/history')
  },

  /** 当前市场状态 + 权重 */
  getMarketState() {
    return client.get<{ success: boolean; data: FusionMarketState }>('/api/v1/fusion-pick/market-state')
  },

  /** 历史选股回测 */
  getBacktest(limit = 30) {
    return client.get<{ success: boolean; data: FusionBacktestResult }>(
      '/api/v1/fusion-pick/backtest', { params: { limit } },
    )
  },

  /** 权重优化建议信号 */
  getOptimizationSignals() {
    return client.get<{ success: boolean; data: FusionOptSignals }>(
      '/api/v1/fusion-pick/backtest/optimization-signals',
    )
  },

  /** 手动触发权重优化（管理员） */
  optimizeWeights() {
    return client.post<{ success: boolean; data: any }>('/api/v1/fusion-pick/optimize-weights')
  },

  /** 取消运行 */
  cancel() {
    return client.post<{ success: boolean; message?: string }>('/api/v1/fusion-pick/cancel')
  },

  /** 重置历史/回测数据（管理员）。scope: snapshots | results | all */
  resetData(scope: 'snapshots' | 'results' | 'all' = 'all') {
    return client.post<{ success: boolean; data: { scope: string; deleted: Record<string, number> } }>(
      '/api/v1/fusion-pick/reset-data', { scope },
    )
  },
}

export type MarketStateKey = 'bull' | 'bear' | 'volatile'
export type DimWeights = { fundamental: number; technical: number; fund_flow: number; valuation: number }

export interface FusionPickProgress {
  is_running: boolean
  progress: number
  status: string
}

export interface FusionPickItem {
  code: string
  name: string
  industry: string
  fusion_score: number
  factor_score: number
  debate_bonus: number
  source_bonus: number
  consensus_level: number
  tendency: number
  source_count: number
  sources: string[]
  scores: Record<string, number>
  score_details: Record<string, any>
  debate_signals: any[]
  debate_consensus: {
    tendency: number
    consensus_level: number
    confidence: number
    positive_count: number
    negative_count: number
    neutral_count: number
    agent_count: number
    avg_score?: number
  } | null
  llm: { summary: string; recommendation: string; risk_factors: string[] } | null
  weight: number
}

export interface FusionPickResult {
  run_id?: string
  picks: FusionPickItem[]
  market_state: MarketStateKey
  market_description: string
  weights_used: DimWeights
  ai_summary: string
  universe_count: number
  filtered_count: number
  candidate_count: number
  strategy_count: number
  mode: 'full' | 'quick'
  timestamp: string
}

export interface FusionHistoryItem {
  run_id: string
  timestamp: string
  market_state: MarketStateKey
  universe_count: number
  candidate_count: number
  selected_count: number
  mode: 'full' | 'quick'
}

export interface FusionMarketState {
  state: MarketStateKey
  description: string
  weights_auto: DimWeights
  weights_optimized: DimWeights | null
  last_optimized_at: string | null
}

export interface HorizonAgg {
  n: number
  avg: number | null
  win_rate: number | null
  baseline: number | null
  excess: number | null
  beat_rate: number | null
}

export interface FusionBacktestResult {
  runs_count: number
  horizons: number[]
  overall: Record<string, HorizonAgg>
  by_market_state: Record<MarketStateKey, { n: number; win_rate: number | null; avg_return: number | null }>
  by_source: {
    quant_only: { n: number; win_rate: number | null }
    multi_source: { n: number; win_rate: number | null }
  }
  fusion_score_correlation: number
  factor_score_correlation: number
  debate_bonus_effectiveness: number
  runs: any[]
}

export interface FusionOptSignals {
  state_performance: Record<MarketStateKey, { win_rate: number | null; sample_size: number }>
  dimension_correlations: Record<MarketStateKey, DimWeights>
  suggested_weights: Record<MarketStateKey, DimWeights>
  sample_counts: Record<MarketStateKey, number>
  reliable: boolean
}
