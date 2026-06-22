import client from './client'

export interface ResearchReport {
  code: string
  name: string
  title: string
  date: string
  org: string
  industry: string
  rating: string
  target_price_high: number | null
  target_price_low: number | null
  abstract: string
  generated_abstract?: string
  cached_at: string
  report_id: string
  pdf_url?: string
  info_code?: string
}

export interface ResearchReportQuery {
  keyword?: string
  code?: string
  org?: string
  days?: number
  page?: number
  page_size?: number
  ratings?: string
  industry?: string
  author?: string
  sort_by?: string
  sort_order?: string
}

export const RATING_OPTIONS = [
  { label: '买入', value: '买入' },
  { label: '增持', value: '增持' },
  { label: '推荐', value: '推荐' },
  { label: '持有', value: '持有' },
  { label: '中性', value: '中性' },
  { label: '减持', value: '减持' },
  { label: '卖出', value: '卖出' },
]

export const researchReportsApi = {
  search(params: ResearchReportQuery = {}) {
    return client.get<{
      success: boolean
      data: ResearchReport[]
      total: number
      page: number
      page_size: number
    }>('/api/v1/research-reports', { params })
  },

  getCodes() {
    return client.get<{
      success: boolean
      data: { code: string; name: string; count: number }[]
    }>('/api/v1/research-reports/codes')
  },

  getOrgs() {
    return client.get<{
      success: boolean
      data: { org: string; count: number }[]
    }>('/api/v1/research-reports/orgs')
  },

  getIndustries() {
    return client.get<{
      success: boolean
      data: { industry: string; count: number }[]
    }>('/api/v1/research-reports/industries')
  },

  summarize(reportId: string) {
    return client.post<{
      success: boolean
      data: { abstract: string; cached: boolean }
    }>('/api/v1/research-reports/summarize', { report_id: reportId })
  },

  getRatingSignals(params: { days?: number; limit?: number } = {}) {
    return client.get<{
      success: boolean
      data: RatingSignal[]
    }>('/api/v1/research-reports/rating-signals', { params })
  },

  getStockReports(code: string, params: { days?: number } = {}) {
    return client.get<{
      success: boolean
      data: ResearchReport[]
    }>(`/api/v1/research-reports/stock/${code}`, { params })
  },

  getStats() {
    return client.get<{
      success: boolean
      data: {
        total: number
        weekly: number
        summarized: number
        ratings: { rating: string; count: number }[]
        top_orgs: { org: string; count: number }[]
      }
    }>('/api/v1/research-reports/stats')
  },
}

export interface RatingSignal {
  code: string
  name: string
  from_rating: string
  to_rating: string
  direction: 'upgrade' | 'downgrade'
  org: string
  date: string
  title: string
  report_id: string
  detected_at: string
}
