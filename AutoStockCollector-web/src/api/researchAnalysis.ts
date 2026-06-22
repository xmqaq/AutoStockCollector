import client from './client'

export interface ChainViewItem {
  sector: string
  link: string
  judgment: string
  bottleneck_score: number
  frequency: number
  confidence: number
}

export interface Candidate {
  code: string
  name: string
  score: number
  score_label: string
  roe: number
  pe: number
  pb: number
  industry: string
  market_cap: number
  mention_count: number
  sectors: string[]
  confidence: number
}

export interface SectorDetail {
  report_count: number
  source: string
  error?: string
}

export interface AnalysisResult {
  success: boolean
  sectors: string[]
  chain_view: ChainViewItem[]
  candidates: Candidate[]
  candidate_count: number
  report_md: string
  elapsed_seconds: number
  sector_details: Record<string, SectorDetail>
  task_id?: string
}

export interface TaskStatus {
  success: boolean
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  message: string
  data?: AnalysisResult
}

export interface HistoryItem {
  task_id: string
  sectors: string[]
  top_n: number
  created_at: string
  result?: AnalysisResult
}

export interface SectorInfo {
  name: string
  description: string
  stock_count: number
  link_count: number
}

export const researchApi = {
  /** 获取行业列表（动态加载） */
  listSectors() {
    return client.get<{ success: boolean; count: number; data: SectorInfo[] }>(
      '/api/v1/ai/research-analysis/sectors',
    )
  },
  /** 启动研报分析（异步） */
  run(sectors: string[], topN = 10) {
    return client.post<{ success: boolean; task_id: string; message: string }>(
      '/api/v1/ai/research-analysis', { sectors, top_n: topN },
    )
  },
  /** 轮询进度 */
  getResult(taskId: string) {
    return client.get<TaskStatus>(`/api/v1/ai/research-analysis/result/${taskId}`)
  },
  /** 获取历史记录 */
  getHistory() {
    return client.get<{ success: boolean; count: number; data: HistoryItem[] }>(
      '/api/v1/ai/research-analysis/history',
    )
  },
  /** 导出 Markdown 简报 */
  exportReport(taskId: string) {
    return client.get(`/api/v1/ai/research-analysis/export/${taskId}`, { responseType: 'blob' })
  },
}
