import { useThemeStore } from '@/stores/themeStore'

export interface ChartTheme {
  textColor: string
  textColorStrong: string
  axisLineColor: string
  splitLineColor: string
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
  legendText: string
}

const dark: ChartTheme = {
  textColor: '#94a3b8',
  textColorStrong: '#f8fafc',
  axisLineColor: '#3b4758',
  splitLineColor: '#2a3441',
  tooltipBg: '#1e2532',
  tooltipBorder: '#3b4758',
  tooltipText: '#f8fafc',
  legendText: '#cbd5e1',
}

const light: ChartTheme = {
  textColor: '#64748b',
  textColorStrong: '#0f172a',
  axisLineColor: '#cbd5e1',
  splitLineColor: '#e2e8f0',
  tooltipBg: '#ffffff',
  tooltipBorder: '#cbd5e1',
  tooltipText: '#0f172a',
  legendText: '#334155',
}

export function getChartTheme(): ChartTheme {
  return useThemeStore().theme === 'dark' ? dark : light
}
