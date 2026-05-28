import dayjs from 'dayjs'

export const RISE_COLOR = '#ef5350'  // A股上涨红
export const FALL_COLOR = '#26a69a'  // A股下跌绿
export const FLAT_COLOR = '#9e9e9e'

export function fmtAmount(n: number): string {
  if (n === undefined || n === null || isNaN(n)) return '--'
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(2)}万`
  return n.toLocaleString()
}

export function fmtChange(rate: number): string {
  if (rate === undefined || rate === null || isNaN(rate)) return '--'
  return `${rate >= 0 ? '+' : ''}${rate.toFixed(2)}%`
}

export function getChangeColor(rate: number): string {
  if (rate > 0) return RISE_COLOR
  if (rate < 0) return FALL_COLOR
  return FLAT_COLOR
}

export function fmtDate(date: string | Date | undefined, format = 'YYYY-MM-DD'): string {
  if (!date) return '--'
  return dayjs(date).format(format)
}

export function fmtDateTime(date: string | Date | undefined): string {
  if (!date) return '--'
  return dayjs(date).format('YYYY-MM-DD HH:mm:ss')
}

export function fmtNumber(n: number | undefined, decimals = 2): string {
  if (n === undefined || n === null || isNaN(n)) return '--'
  return n.toFixed(decimals)
}

export function fmtPercent(n: number | undefined): string {
  if (n === undefined || n === null || isNaN(n)) return '--'
  return `${(n * 100).toFixed(2)}%`
}
