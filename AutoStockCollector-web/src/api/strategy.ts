import client from './client'
import type { StrategyRule, IndicatorItem } from '@/types'

export interface ApiResponseData<T> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

export const strategyApi = {
  /** 获取策略列表 */
  list(type?: 'selection' | 'trading', enabledOnly?: boolean) {
    const params: Record<string, string> = {}
    if (type) params.type = type
    if (enabledOnly) params.enabled_only = 'true'
    return client.get<ApiResponseData<StrategyRule[]>>('/api/v1/strategies', { params })
  },

  /** 获取单个策略 */
  get(id: string) {
    return client.get<ApiResponseData<StrategyRule>>(`/api/v1/strategies/${id}`)
  },

  /** 创建策略 */
  create(data: Partial<StrategyRule>) {
    return client.post<ApiResponseData<StrategyRule>>('/api/v1/strategies', data)
  },

  /** 更新策略 */
  update(id: string, data: Partial<StrategyRule>) {
    return client.put<ApiResponseData<StrategyRule>>(`/api/v1/strategies/${id}`, data)
  },

  /** 删除策略 */
  delete(id: string) {
    return client.delete<ApiResponseData<null>>(`/api/v1/strategies/${id}`)
  },

  /** 获取可选指标目录 */
  getIndicators() {
    return client.get<ApiResponseData<IndicatorItem[]>>('/api/v1/strategies/indicators')
  },

  /** 获取内置预设策略 */
  getPresets(type?: 'selection' | 'trading') {
    const params: Record<string, string> = {}
    if (type) params.type = type
    return client.get<ApiResponseData<StrategyRule[]>>('/api/v1/strategies/presets', { params })
  },

  /** 应用预设策略（清空后重建） */
  applyPresets() {
    return client.post<ApiResponseData<StrategyRule[]>>('/api/v1/strategies/presets/apply')
  },

  /** 应用选股策略到量化选股 */
  applyToPicker(id: string, params?: { top_n?: number; candidate_pool?: number }) {
    return client.post<ApiResponseData<{ message: string; strategy: string }>>(
      `/api/v1/strategies/${id}/apply`, params || {}
    )
  },

  /** 异步测试选股策略（后台运行） */
  testToPicker(id: string, params?: { top_n?: number; candidate_pool?: number }) {
    return client.post<ApiResponseData<{ strategy: string; message: string }>>(
      `/api/v1/strategies/${id}/test`, params || {},
    )
  },

  /** 轮询测试结果 */
  getTestResult() {
    return client.get<ApiResponseData<{
      is_running: boolean
      progress: number
      status: string
      strategy: string
      picks: StrategyTestPick[]
      candidate_count: number
      universe_count: number
      filtered_count: number
      filtered_detail: Record<string, number>
      timestamp: string
    }>>('/api/v1/strategies/test/result')
  },
}

export interface StrategyTestPick {
  code: string
  name: string
  industry: string
  composite: number
  dim_scores: Record<string, number>
}
