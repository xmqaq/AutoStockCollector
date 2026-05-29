export type CollectCategory = 'range' | 'snapshot' | 'catalog'

export interface CollectTypeMeta {
  value: string
  label: string
  category: CollectCategory
}

export const COLLECT_TYPES: CollectTypeMeta[] = [
  { value: 'kline', label: 'K线数据', category: 'range' },
  { value: 'financial', label: '财务数据', category: 'range' },
  { value: 'dragon_tiger', label: '龙虎榜', category: 'range' },
  { value: 'margin', label: '融资融券', category: 'range' },
  { value: 'news', label: '新闻资讯', category: 'snapshot' },
  { value: 'fund_flow', label: '资金流向', category: 'snapshot' },
  { value: 'sector', label: '板块数据', category: 'snapshot' },
  { value: 'stock_info', label: '股票信息', category: 'catalog' },
]

export const RANGE_TYPES = COLLECT_TYPES.filter(t => t.category === 'range')
export const TYPE_LABEL: Record<string, string> =
  Object.fromEntries(COLLECT_TYPES.map(t => [t.value, t.label]))
