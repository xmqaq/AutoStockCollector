export function pnlColorClass(v: number) {
  if (v > 0) return 'text-rise'
  if (v < 0) return 'text-fall'
  return 'text-neutral'
}

export function formatAmount(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万'
  return v.toFixed(2)
}

export function formatPercent(v: number): string {
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}