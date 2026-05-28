// Stock code format: SH600000 or SZ000001

export interface KlineRecord {
  code: string
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
  change_rate: number
  turnover_rate?: number
}

export interface DragonTigerRecord {
  code: string
  name: string
  date: string
  reason: string
  total_amount: number
  net_buy: number
  close?: number
  change_rate?: number
}

export interface MarginRecord {
  code: string
  date: string
  rz_balance: number
  rz_buy: number
  rq_volume: number
  rq_sell: number
}

export interface SectorRecord {
  name: string
  type: string
  net_flow: number
  change_rate: number
}

export interface StockInfo {
  code: string
  name: string
  industry?: string
  area?: string
  pe?: number
  pb?: number
  total_mv?: number
  circ_mv?: number
  list_date?: string
}

export interface FinancialRecord {
  code: string
  report_date: string
  roe?: number
  roa?: number
  net_profit?: number
  revenue?: number
  eps?: number
  bps?: number
  [key: string]: unknown
}

export interface NewsRecord {
  title: string
  content?: string
  summary?: string
  datetime?: string
  date?: string
  publish_date?: string
  source?: string
  url?: string
}

export interface FundFlowRecord {
  code: string
  date: string
  main_net_flow?: number
  super_net_flow?: number
  big_net_flow?: number
  mid_net_flow?: number
  small_net_flow?: number
  [key: string]: unknown
}

export interface TaskRecord {
  id?: string
  task_id?: string
  task_type: string
  status: string
  create_time?: string
  created_at?: string
  update_time?: string
  updated_at?: string
  progress?: number
  total?: number
  success?: number
  failed?: number
  error_msg?: string
  error_message?: string
}

export interface CollectProgress {
  task_type: string
  status: string
  progress: number
  total: number
  percent: number
  success: number
  failed: number
  task_id?: string
  elapsed_time?: number
  record_count?: number
  date_from?: string
  date_to?: string
  last_update?: string
}

export interface WatchlistItem {
  code: string
  name?: string
  group_id?: string
  priority?: number
  add_time?: string
  added_at?: string
  latest_price?: number | null
  latest_date?: string | null
}

export interface WatchlistGroup {
  id: string
  group_id?: string
  name: string
  stock_count?: number
}

export interface StrategyItem {
  name: string
  description?: string
  id?: string
}

export interface BacktestResult {
  strategy: string
  codes: string[]
  start_date: string
  end_date: string
  initial_cash: number
  total_return?: number
  annual_return?: number
  max_drawdown?: number
  win_rate?: number
  sharpe_ratio?: number
  equity_curve?: { date: string; value: number }[]
  [key: string]: unknown
}

export interface AIAnalysisResult {
  code: string
  type: string
  score?: number
  conclusion?: string
  logic?: string
  risks?: string
  timestamp?: string
  [key: string]: unknown
}

export interface ApiResponse<T = unknown> {
  success: boolean
  data?: T
  message?: string
  error?: string
}
