import client from './client'

export interface AIKeyConfig {
  provider: string
  name: string
  enabled: boolean
  priority: number
  has_key?: boolean
  updated_at?: string
  api_key?: string
  base_url?: string
  model?: string
}

export interface PickedStock {
  code: string
  total: number
  scores: Record<string, number>
}

export interface BatchTask {
  task_id: string
  status: string
  total: number
  completed: number
  failed: number
  current?: string
  results: unknown[]
  errors: unknown[]
}

export interface MultiAgentTask {
  task_id: string
  status: string
  code: string
  agents: Record<string, AgentState>
  aggregated_result?: AggregatedResult
}

export interface AgentState {
  id: string
  name: string
  role: string
  status: 'idle' | 'analyzing' | 'completed' | 'error'
  progress: number
  result?: AgentResult
  error?: string
}

export interface AgentResult {
  score?: number
  conclusion?: string
  signals?: string[]
  metrics?: Record<string, number>
  recommendation?: string
}

export interface AggregatedResult {
  code: string
  compositeScore: number
  recommendation: string
  avgScore: number
  signals: string[]
  agentResults: AgentResult[]
  generatedAt: string
}

export interface SentimentTrend {
  date: string
  score: number
  positive: number
  neutral: number
  negative: number
}

export interface BacktestReport {
  strategy: string
  codes: string[]
  start_date: string
  end_date: string
  initial_cash: number
  final_value: number
  total_return: number
  annual_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  total_trades: number
  equity_curve: { date: string; value: number }[]
  monthly_stats: { month: string; return: number }[]
  sample_trades: TradeRecord[]
}

export interface TradeRecord {
  date: string
  code: string
  type: 'buy' | 'sell'
  price: number
  amount: number
  pnl: number
  reason: string
}

export interface WinRateStats {
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_pnl: number
  avg_profit: number
  avg_loss: number
  profit_loss_ratio: number
}

export const aiKeyApi = {
  list() {
    return client.get('/api/v1/ai-keys')
  },
  update(data: Partial<AIKeyConfig> & { api_key?: string }) {
    return client.post('/api/v1/ai-keys', data)
  },
  remove(provider: string) {
    return client.delete(`/api/v1/ai-keys/${provider}`)
  },
  test(provider: string, apiKey?: string, baseUrl?: string) {
    return client.post(`/api/v1/ai-keys/${provider}/test`, { api_key: apiKey, base_url: baseUrl })
  },
  reorder(priorities: { provider: string; priority: number }[]) {
    return client.put('/api/v1/ai-keys/reorder', { priorities })
  },
  fetchModels(provider: string) {
    return client.get(`/api/v1/ai-keys/${provider}/models`)
  },
}

export const pickerApi = {
  smartPick(topN = 10, factors = ['trend', 'volume', 'value', 'fund_flow']) {
    return client.post('/api/v1/pick/smart', { top_n: topN, factors })
  },
  smartPickAdvanced(params: { strategy: string; top_n: number; min_score?: number }) {
    return client.post('/api/v1/pick/smart-advanced', params)
  },
}

export const aiApi = {
  analyze(params: { code: string; type: string }) {
    return client.post('/api/v1/ai/analyze', params)
  },
  list() {
    return client.get('/api/v1/ai-keys')
  },
  analyzeStock(params: { code: string }) {
    return client.post('/api/v1/ai/analyze', params)
  },
  analyzeNews(params: { news: Record<string, unknown> }) {
    return client.post('/api/v1/ai/analyze-news', params)
  },
  batchAnalyze(params: { codes: string[]; type?: string }) {
    return client.post('/api/v1/ai/batch-analyze', params)
  },
  getBatchProgress(taskId: string) {
    return client.get(`/api/v1/ai/batch-progress/${taskId}`)
  },
  multiAgentAnalyze(params: { code: string; type?: string }) {
    return client.post('/api/v1/ai/multi-agent', params)
  },
  getMultiAgentProgress(taskId: string) {
    return client.get(`/api/v1/ai/multi-agent/${taskId}`)
  },
  chat(params: { message: string; model?: string; provider?: string; history?: { role: string; content: string }[] }) {
    return client.post('/api/v1/ai/chat', params)
  },
  chatStream(params: { message: string; provider?: string; history?: { role: string; content: string }[] }) {
    return fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
  },
}

export const sentimentApi = {
  getTrend(code?: string, days = 30) {
    return client.get('/api/v1/sentiment/trend', { params: { code, days } })
  },
  getEvents(code?: string, limit = 20) {
    return client.get('/api/v1/sentiment/events', { params: { code, limit } })
  },
  getKeywords(code?: string) {
    return client.get('/api/v1/sentiment/keywords', { params: { code } })
  },
  getNewsSentiment(code?: string, limit = 20) {
    return client.get('/api/v1/sentiment/news-sentiment', { params: { code, limit } })
  },
  getSummary(code?: string) {
    return client.get('/api/v1/sentiment/summary', { params: { code } })
  },
}

export const backtestEnhancedApi = {
  getReport(params: {
    strategy: string
    codes: string[]
    start_date: string
    end_date: string
    initial_cash: number
  }) {
    return client.post('/api/v1/backtest/enhanced/report', params)
  },
  getEquityCurve(initialCash = 1000000, days = 90) {
    return client.post('/api/v1/backtest/enhanced/equity', { initial_cash: initialCash, days })
  },
  getTrades(codes: string[], limit = 50) {
    return client.post('/api/v1/backtest/enhanced/trades', { codes, limit })
  },
  getMonthlyStats() {
    return client.post('/api/v1/backtest/enhanced/monthly')
  },
  getWinRateAnalysis(codes: string[]) {
    return client.post('/api/v1/backtest/enhanced/win-rate', { codes })
  },
}

// ── 深度分析 v2 ──────────────────────────────
export interface DeepBasicInfo {
  code: string
  name: string
  industry: string
  market_cap_yi: number | null
  list_date: string | null
}

export interface DeepPriceInfo {
  current_price: number | null
  price_change_pct: number | null
  high_52w: number | null
  low_52w: number | null
  volume_ratio: number | null
}

export interface DeepKlineItem {
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
}

export interface DeepFinancialHistory {
  report_date: string
  report_type: string
  revenue_yi: number | null
  net_profit_yi: number | null
  roe: number | null
  gross_margin: number | null
}

export interface DeepFinancial {
  report_date: string | null
  report_type: string
  roe: number | null
  revenue_yi: number | null
  revenue_growth: number | null
  net_profit_yi: number | null
  profit_growth: number | null
  gross_margin: number | null
  debt_ratio: number | null
  eps: number | null
  net_asset_ps: number | null
  pe: number | null
  pb: number | null
  history: DeepFinancialHistory[]
}

export interface DeepFundFlow {
  date: string | null
  main_net_inflow: number | null
  main_net_inflow_yi: number | null
  inflow_ratio: number | null
  turnover_rate: number | null
  total_amount: number | null
  total_amount_yi: number | null
  avg5_main_net_inflow_yi: number | null
  avg5_turnover_rate: number | null
}

export interface DeepTechnical {
  ma5: number | null
  ma20: number | null
  ma60: number | null
  macd_dif: number | null
  macd_dea: number | null
  macd_bar: number | null
  rsi14: number | null
  momentum_20d: number | null
  trend: string
  macd_signal: string
  data_available: boolean
}

export interface DeepScoreDim {
  score: number | null
  details: Record<string, any>
}

export interface DeepScores {
  fundamental: DeepScoreDim
  technical: DeepScoreDim
  fund_flow: DeepScoreDim
  valuation: DeepScoreDim
  composite: number | null
}

export interface DeepNewsItem {
  title: string
  publish_time: string
  source: string
  content: string
}

export interface DeepAnalysisData {
  basic_info: DeepBasicInfo
  price_info: DeepPriceInfo
  kline: DeepKlineItem[]
  financial: DeepFinancial
  fund_flow: DeepFundFlow
  technical: DeepTechnical
  scores: DeepScores
  news: DeepNewsItem[]
  analysis_time: string
}

export interface AIReportResult {
  success: boolean
  content?: string
  provider?: string
  from_cache?: boolean
  error?: string
}

// ── 第二期一体化 AI 服务（旧接口保留兼容） ──────────────────────────────
export interface AIScores {
  technical: number
  fundamental: number
  fund_flow: number
  valuation: number
  composite: number
}

export interface AIAnalysisResult {
  code: string
  name: string
  scores: AIScores
  current_price: number | null
  llm: { summary: string; recommendation: string; risk_factors: string[] } | null
  source: 'llm' | 'factor'
}

export interface AIAdvice {
  action: string
  reason: string
  buy_zone: string
  stop_loss: string
  position_advice: string
}

export interface AIAdviceResult {
  code: string
  name: string
  composite: number
  current_price: number | null
  advice: AIAdvice
  source: 'llm' | 'rule'
}

export interface AIPick {
  code: string
  name: string
  composite: number
  scores: Record<string, number>
  score_details: Record<string, any>
  recommendation: string
  source: string
  industry?: string
}

export interface AIPickResult {
  strategy: string
  picks: AIPick[]
  ai_summary?: string
  candidate_count?: number
  universe_count?: number
  timestamp: string
}

export const deepAnalysisApi = {
  getData(code: string) {
    return client.get(`/api/v1/stock/deep_analysis/${code}`)
  },
  getAIReport(code: string) {
    return client.post(`/api/v1/stock/deep_analysis/${code}/ai`)
  },
}

export const aiServiceApi = {
  analysis(code: string) {
    return client.get(`/api/v1/ai/stock/${code}/analysis`)
  },
  advice(code: string, payload: { cost?: number; position?: number } = {}) {
    return client.post(`/api/v1/ai/stock/${code}/advice`, payload)
  },
  pickRun(payload: { strategy?: string; top_n?: number; candidate_pool?: number } = {}) {
    return client.post('/api/v1/ai/pick/run', payload)
  },
  pickResults() {
    return client.get('/api/v1/ai/pick/results')
  },
  pickProgress() {
    return client.get('/api/v1/ai/pick/progress')
  },
}

export interface AIAgent {
  id: string
  name: string
  description: string
  role: string
  system_prompt: string
  temperature: number
  max_tokens: number
  enabled: boolean
  priority: number
  created_at?: string
  updated_at?: string
}

export const aiAgentApi = {
  list() {
    return client.get('/api/v1/ai-agents')
  },
  get(id: string) {
    return client.get(`/api/v1/ai-agents/${id}`)
  },
  create(data: Partial<AIAgent>) {
    return client.post('/api/v1/ai-agents', data)
  },
  update(id: string, data: Partial<AIAgent>) {
    return client.put(`/api/v1/ai-agents/${id}`, data)
  },
  delete(id: string) {
    return client.delete(`/api/v1/ai-agents/${id}`)
  },
  test(id: string, message?: string, code?: string) {
    return client.post(`/api/v1/ai-agents/${id}/test`, { message, code })
  },
  analyze(id: string, code: string) {
    return client.post(`/api/v1/ai-agents/${id}/analyze`, { code })
  },
  analyzeStream(id: string, code: string) {
    return client.post(`/api/v1/ai-agents/${id}/analyze/stream`, { code })
  },
  getHistory(params: { page?: number; page_size?: number; agent_id?: string; code?: string }) {
    return client.get('/api/v1/ai-agents/history', { params })
  },
  saveHistory(data: {
    agent_id: string
    stock_code: string
    stock_name?: string
    content?: string
    score?: number
    recommendation?: string
    provider?: string
    duration_ms?: number
  }) {
    return client.post('/api/v1/ai-agents/history', data)
  },
  compare(codes: string[]) {
    return client.post('/api/v1/ai-agents/compare', { codes })
  },
  batchAnalyze(codes: string[], agentId?: string) {
    return client.post('/api/v1/ai-agents/batch-analyze', { codes, agent_id: agentId })
  },
}

export const agentApi = {
  analyze(agentId: string, code: string) {
    return client.post(`/api/v1/ai-agents/${agentId}/analyze`, { code })
      .then((res: any) => res.data || res)
  },
}

// ── 多空辩论 + 风险管控 ──────────────────────────────
export interface DebateAgentState {
  status: 'idle' | 'running' | 'completed' | 'error'
  progress: number
  result?: {
    content: string
    score?: number
    stance: 'bullish' | 'bearish' | 'verdict'
  }
  error?: string
}

export interface DebateTask {
  task_id: string
  code: string
  status: string
  debate: {
    bull: DebateAgentState
    bear: DebateAgentState
    judge: DebateAgentState
  }
  final_verdict?: FinalVerdict
}

export interface FinalVerdict {
  code: string
  bullScore: number
  bearScore: number
  tendency: string
  riskLevel: string
  recommendation: string
  bullArgument: string
  bearArgument: string
  judgeVerdict: string
  generatedAt: string
}

export const orchestrationApi = {
  analyze(params: { code: string }) {
    return client.post('/api/v1/ai/orchestrate', params)
  },
  analyzeStream(params: { code: string }) {
    return fetch('/api/v1/ai/orchestrate/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
  },
}

export const reflectionApi = {
  getForStock(code: string) {
    return client.get(`/api/v1/ai-agents/reflections/${code}`)
  },
}

export const skillApi = {
  list() {
    return client.get('/api/v1/ai-agents/skills')
  },
  get(name: string) {
    return client.get(`/api/v1/ai-agents/skills/${name}`)
  },
}

// ── 投资哲学 Agent ──────────────────────────────
export interface PhilosophyAgent {
  id: string
  name: string
  school: string
  school_label?: string
  description: string
  enabled?: boolean
}

export interface PhilosophyAgentDetail {
  agent_id: string
  name: string
  archetype: string
  description: string
  system_prompt: string
  temperature: number
  max_tokens: number
  risk_tolerance: number
  holding_horizon: string
  weight_dimensions: Record<string, number>
}

export interface PhilosophySignal {
  agent_id: string
  agent_name: string
  philosophy?: string
  archetype?: string
  score: number
  action: string
  confidence: number
  reasoning: string
  signals: string[]
  key_factors?: string[]
  risk_warnings?: string[]
}

export interface PhilosophyConsensus {
  tendency: number
  consensus_level: number
  confidence: number
  high_conviction: boolean
  positive_count: number
  negative_count: number
}

export interface PhilosophyVerdict {
  code: string
  agent_signals: PhilosophySignal[]
  consensus: PhilosophyConsensus
}

export const philosophyApi = {
  listAgents() {
    return client.get('/api/v1/ai/philosophy/agents')
  },
  stream(params: { code: string; agents: string[] }) {
    return fetch('/api/v1/ai/philosophy/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
  },
  analyze(params: { code: string; agents: string[] }) {
    return client.post('/api/v1/ai/philosophy/analyze', params)
  },
}

// ── Research-Battle ──────────────────────────────
export const researchBattleApi = {
  stream(params: { code: string; num_rounds?: number; user_id?: string }) {
    return fetch('/api/v1/ai/research-battle/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
  },
  quick(params: { code: string; num_rounds?: number; user_id?: string }) {
    return client.post('/api/v1/ai/research-battle/quick', params)
  },
}

