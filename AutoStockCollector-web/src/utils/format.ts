import dayjs from 'dayjs'

export const RISE_COLOR = '#ef5350'  // A股上涨红
export const FALL_COLOR = '#26a69a'  // A股下跌绿
export const FLAT_COLOR = '#9e9e9e'

function toNum(v: unknown): number | null {
  if (v === undefined || v === null || v === '') return null
  if (typeof v === 'number') return isNaN(v) ? null : v
  if (typeof v === 'string') {
    // 兼容后端原样返回的中文数字字符串："178.61亿" / "1.49%" / "22.63"
    const s = v.trim()
    if (!s) return null
    const pctMatch = s.match(/^(-?\d+(?:\.\d+)?)\s*%$/)
    if (pctMatch) return parseFloat(pctMatch[1])
    const yiMatch = s.match(/^(-?\d+(?:\.\d+)?)\s*亿$/)
    if (yiMatch) return parseFloat(yiMatch[1]) * 1e8
    const wanMatch = s.match(/^(-?\d+(?:\.\d+)?)\s*万$/)
    if (wanMatch) return parseFloat(wanMatch[1]) * 1e4
    const f = parseFloat(s)
    return isNaN(f) ? null : f
  }
  return null
}

export function fmtAmount(n: number | string | null | undefined): string {
  const num = toNum(n)
  if (num === null) return '--'
  const abs = Math.abs(num)
  const sign = num < 0 ? '-' : ''
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${sign}${(abs / 1e4).toFixed(2)}万`
  return num.toLocaleString()
}

export function fmtChange(rate: number | string | null | undefined): string {
  const num = toNum(rate)
  if (num === null) return '--'
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`
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

export function fmtNumber(n: number | string | null | undefined, decimals = 2): string {
  const num = toNum(n)
  if (num === null) return '--'
  return num.toFixed(decimals)
}

export function fmtPercent(n: number | string | null | undefined): string {
  const num = toNum(n)
  if (num === null) return '--'
  return `${(num * 100).toFixed(2)}%`
}
