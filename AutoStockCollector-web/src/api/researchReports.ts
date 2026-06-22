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
}

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

  summarize(reportId: string) {
    return client.post<{
      success: boolean
      data: { abstract: string; cached: boolean }
    }>('/api/v1/research-reports/summarize', { report_id: reportId })
  },
}
