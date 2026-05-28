export interface KlineRecord {
  code: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  change_rate: number;
}

export interface StockInfo {
  code: string;
  name: string;
  market: string;
  industry: string;
  list_date: string;
  total_share: number;
  float_share: number;
}

export interface FinancialRecord {
  code: string;
  report_date: string;
  revenue: number;
  net_profit: number;
  eps: number;
  roe: number;
  net_asset: number;
}

export interface NewsItem {
  id: string;
  code: string;
  title: string;
  content: string;
  publish_time: string;
  source: string;
  url: string;
}

export interface FundFlowRecord {
  code: string;
  date: string;
  volume: number;
  amount: number;
  direction: 'buy' | 'sell';
  price: number;
}

export interface DragonTigerRecord {
  code: string;
  name: string;
  date: string;
  reason: string;
  total_amount: number;
  net_buy: number;
}

export interface SectorItem {
  name: string;
  type: string;
  net_flow: number;
  change_rate: number;
}

export interface MarginRecord {
  code: string;
  date: string;
  rz_balance: number;
  rz_buy: number;
  rq_volume: number;
  rq_sell: number;
}

export interface TaskProgress {
  task_id: string;
  task_type: string;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  total: number;
  success: number;
  failed: number;
  duration: number;
  message?: string;
  error_message?: string;
  create_time?: string;
}

export interface CollectProgressResponse {
  success: boolean;
  data?: {
    all_done?: boolean;
    tasks?: TaskProgress[];
  };
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  count?: number;
  message?: string;
}