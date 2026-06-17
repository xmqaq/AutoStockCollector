import type { StrategyRule, IndicatorItem } from '@/types'

export const dimLabels: Record<string, string> = {
  fundamental: '基本面', technical: '技术面', fund_flow: '资金面', valuation: '估值面',
  entry: '买入信号', exit: '卖出信号',
}

export function dimLabel(d: string) { return dimLabels[d] || d }

export function dimColor(d: string) {
  const c: Record<string, string> = {
    fundamental: '#3f7fae', technical: '#c9943a', fund_flow: '#3f9d70',
    valuation: '#d05a51', entry: '#909399', exit: '#909399',
  }
  return c[d] || '#909399'
}

export function paramLabel(k: string): string {
  const map: Record<string, string> = {
    min: '最小值', max: '最大值', threshold: '阈值',
    fast: '快线周期', slow: '慢线周期', volume_ratio: '量比阈值',
    loss_pct: '止损%', profit_pct: '止盈%', grid_pct: '网格%',
    max_grids: '最大网格', ratio: '放量倍数',
  }
  return map[k] || k
}

export function weightTooltip(item: StrategyRule) {
  return Object.entries(item.weights || {})
    .map(([k, v]) => `${dimLabel(k)} ${Math.round(v * 100)}%`).join(' | ')
}

export function enabledCount(item: StrategyRule) { return (item.indicators || []).filter(i => i.enabled).length }
export function totalCount(item: StrategyRule) { return (item.indicators || []).length }
export function hasParams(ind: IndicatorItem) { return ind.params && Object.keys(ind.params).length > 0 }

export function filterSummary(item: StrategyRule) {
  const f = item.filters || {}
  const parts: string[] = []
  if (f.exclude_st !== false) parts.push('去ST')
  if (f.min_kline_bars) parts.push(`K线≥${f.min_kline_bars}`)
  if (f.min_avg_amount) parts.push(`成交≥${(Number(f.min_avg_amount) / 1e8).toFixed(1)}亿`)
  return parts.join(' ') || '默认'
}
