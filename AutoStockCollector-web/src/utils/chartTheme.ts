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
  textColor: '#909399',
  textColorStrong: '#e5eaf3',
  axisLineColor: '#3c3c3c',
  splitLineColor: '#2c2c2c',
  tooltipBg: '#1f1f1f',
  tooltipBorder: '#3c3c3c',
  tooltipText: '#e5eaf3',
  legendText: '#c0c4cc',
}

const light: ChartTheme = {
  textColor: '#909399',
  textColorStrong: '#303133',
  axisLineColor: '#dcdfe6',
  splitLineColor: '#e4e7ed',
  tooltipBg: '#ffffff',
  tooltipBorder: '#dcdfe6',
  tooltipText: '#303133',
  legendText: '#606266',
}

export function getChartTheme(): ChartTheme {
  return useThemeStore().theme === 'dark' ? dark : light
}
