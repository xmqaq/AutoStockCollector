import client from './client'
import type { StrategyRule } from '@/types'

export const strategyPickApi = {
  /** 获取可用选股策略列表 */
  getStrategies() {
    return client.get<{ success: boolean; data: StrategyRule[] }>('/api/v1/strategy-pick/strategies')
  },

  /** 获取可用分析 Agent 列表（含 MongoDB AI Agent 和投资哲学 Agent） */
  getAgents() {
    return client.get<{ success: boolean; data: StrategyPickAgent[] }>('/api/v1/strategy-pick/agents')
  },

  /** 启动策略选股 */
  run(strategyIds: string[], topN = 20, perStrategyTop = 15, agentIds: string[] = [], philosophyIds: string[] = []) {
    return client.post<{ success: boolean; message?: string; error?: string }>(
      '/api/v1/strategy-pick/run',
      {
        strategy_ids: strategyIds, top_n: topN, per_strategy_top: perStrategyTop,
        agent_ids: agentIds, philosophy_ids: philosophyIds,
      },
    )
  },

  /** 查询进度 */
  getProgress() {
    return client.get<{ success: boolean; data: StrategyPickProgress }>('/api/v1/strategy-pick/progress')
  },

  /** 获取结果（可指定 run_id 获取历史） */
  getResult(runId?: string) {
    const params = runId ? { run_id: runId } : {}
    return client.get<{ success: boolean; data: StrategyPickResult }>('/api/v1/strategy-pick/result', { params })
  },

  /** 取消运行 */
  cancel() {
    return client.post<{ success: boolean; message?: string }>('/api/v1/strategy-pick/cancel')
  },

  /** 获取历史结果列表 */
  getHistory() {
    return client.get<{ success: boolean; data: StrategyPickHistoryItem[] }>('/api/v1/strategy-pick/history')
  },
}

export interface StrategyPickAgent {
  id: string
  name: string
  description: string
  role?: string
  archetype?: string
  priority: number
  type: 'llm' | 'philosophy'
}

export interface StrategyPickProgress {
  is_running: boolean
  progress: number
  status: string
}

export interface DebateSignal {
  agent_id: string
  philosophy: string
  archetype: string
  action: string
  confidence: number
  score: number
  reasoning: string
  key_factors: string[]
  risk_warnings: string[]
}

export interface DebateConsensus {
  tendency: number
  consensus_level: number
  confidence: number
  high_conviction: boolean
  positive_count: number
  negative_count: number
  neutral_count: number
  avg_score: number
  agent_count: number
}

export interface DebateEntry {
  code: string
  name: string
  signals: DebateSignal[]
  consensus: DebateConsensus | null
}

export interface StrategyPickItem {
  code: string
  name: string
  industry: string
  composite: number
  scores: Record<string, number>
  score_details: Record<string, any>
  llm: { summary: string; recommendation: string; risk_factors: string[] } | null
  agent_analyses?: { agent_id: string; agent_name: string; summary: string; recommendation: string; risk_factors: string[] }[]
  source: string
  from_strategy: string
  from_strategies: string[]
  strategy_score: number
  agent_analysis?: any
  debate_signals?: DebateSignal[]
  debate_consensus?: DebateConsensus | null
  debate_dim_scores?: Record<string, number>
}

export interface PortfolioSuggestionPosition {
  code: string
  name: string
  industry: string
  composite: number
  action: string
  weight: number
  cumulative: number
}

export interface PortfolioSuggestion {
  positions: PortfolioSuggestionPosition[]
  total_count: number
  industry_count: number
  max_industry_pct: number
  industry_distribution: Record<string, { count: number; pct: number }>
}

export interface TradeSignal {
  code: string
  name: string
  action: string
  priority: string
  composite: number | null
  current_shares: number
  reason: string
}

export interface StrategyPickHistoryItem {
  run_id: string
  strategy_count: number
  selected_count: number
  status?: string
  timestamp?: string
  created_at?: string
  pick_config?: {
    strategy_ids: string[]
    agent_ids: string[]
    philosophy_ids: string[]
    top_n: number
  }
  portfolio_metrics?: PortfolioMetrics
}

export interface PortfolioMetrics {
  avg_composite: number
  composite_std: number
  composite_max: number
  composite_min: number
  industry_count: number
  industry_hhi: number
  top_industry: string
  top_industry_pct: number
  dimension_avg: Record<string, number>
}

export interface StrategyPickResult {
  run_id?: string
  picks: StrategyPickItem[]
  debate_results: DebateEntry[]
  debate_summary: string
  ai_summary: string
  strategy_count: number
  merged_count: number
  selected_count: number
  strategy_stats: Record<string, number>
  trade_signals?: TradeSignal[]
  portfolio_suggestion?: PortfolioSuggestion
  portfolio_metrics?: PortfolioMetrics
  timestamp: string
  created_at?: string
  pick_config?: {
    strategy_ids: string[]
    agent_ids: string[]
    philosophy_ids: string[]
    top_n: number
  }
}

export interface RebalanceOrder {
  code: string
  name: string
  action: 'buy' | 'sell'
  shares: number
  price: number | null
  target_weight: number
  current_weight: number
  reason: string
  skipped: boolean
  skip_reason: string | null
  ai_action?: string
  ai_reason?: string
}

export interface RebalanceAdvice {
  total_value: number
  buffer: number
  cash: number
  orders: RebalanceOrder[]
  message?: string
  mode?: 'quant' | 'ai'
}
