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

export interface MonitorConfig {
  enabled: boolean
  price_rise_threshold: number
  price_fall_threshold: number
  quick_fall_threshold: number
  volume_ratio_threshold: number
  shrink_ratio_threshold: number
  main_flow_threshold: number
  continuous_days: number
  notify_in_app: boolean
  notify_email: boolean
  notify_webhook: boolean
  email: string
  webhook_url: string
}

export interface MonitorStock {
  code: string
  name: string
  price: number
  change_rate: number
  high: number
  low: number
  alert_type: string
  alert_label: string
}

export interface Alert {
  id: string
  code: string
  name: string
  type: 'price' | 'volume' | 'flow' | 'other'
  level: 'info' | 'warning' | 'danger'
  message: string
  detail?: string
  read: boolean
  created_at: string
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
    return client.post('/api/v1/ai/analyze-stock', params)
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
}

export const monitorApi = {
  getConfig(userId = 'default') {
    return client.get(`/api/v1/monitor/config`, { params: { user_id: userId } })
  },
  saveConfig(config: Partial<MonitorConfig>, userId = 'default') {
    return client.post(`/api/v1/monitor/config`, config, { params: { user_id: userId } })
  },
  getStocks(userId = 'default') {
    return client.get(`/api/v1/monitor/stocks`, { params: { user_id: userId } })
  },
  addStock(code: string, name?: string, userId = 'default') {
    return client.post(`/api/v1/monitor/stocks`, { code, name }, { params: { user_id: userId } })
  },
  removeStock(code: string, userId = 'default') {
    return client.delete(`/api/v1/monitor/stocks/${code}`, { params: { user_id: userId } })
  },
  getAlerts(limit = 50, unreadOnly = false) {
    return client.get('/api/v1/monitor/alerts', { params: { limit, unread_only: unreadOnly } })
  },
  markAlertRead(alertId: string) {
    return client.post(`/api/v1/monitor/alerts/${alertId}/read`)
  },
  markAllAlertsRead() {
    return client.post('/api/v1/monitor/alerts/read-all')
  },
  deleteAlert(alertId: string) {
    return client.delete(`/api/v1/monitor/alerts/${alertId}`)
  },
  triggerTestAlert(type = 'price') {
    return client.post('/api/v1/monitor/alerts/trigger', { type })
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
