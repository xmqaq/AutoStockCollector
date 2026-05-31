import type { StrategyItem } from '@/types'

const BUILTIN_STRATEGIES: StrategyItem[] = [
  { id: 'default', name: 'default', description: '综合评分（基本面+技术面）' },
  { id: 'fundamental', name: 'fundamental', description: '基本面优先' },
  { id: 'technical', name: 'technical', description: '技术面优先' },
]

export const strategyApi = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getStrategyList(): Promise<{ data: any }> {
    return Promise.resolve({ data: { strategies: BUILTIN_STRATEGIES } })
  },
}
