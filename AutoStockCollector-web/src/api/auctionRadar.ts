import client from './client'

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

export const auctionRadarApi = {
  getStatus() {
    return client.get<{ success: boolean; data: { status: string; scan_time: string; date: string } }>(
      '/api/v1/ai/pre-market-radar/status',
    )
  },
  getResults() {
    return client.get<{ success: boolean; data: RadarResult }>(
      '/api/v1/ai/pre-market-radar/results',
    )
  },
  triggerScan(symbols?: string[]) {
    return client.post<{ success: boolean; data: RadarResult }>(
      '/api/v1/ai/pre-market-radar/trigger',
      { symbols },
    )
  },
}
