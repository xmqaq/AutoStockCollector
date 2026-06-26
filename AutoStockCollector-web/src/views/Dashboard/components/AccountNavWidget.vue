<template>
  <div class="account-nav-widget" v-loading="loading">
    <div class="widget-header">
      <div class="header-left">
        <h2 class="title"><el-icon><TrendCharts /></el-icon> 模拟盘收益走势</h2>
      </div>
      <el-button class="modern-btn" text @click="router.push('/position')">
        详情 →
      </el-button>
    </div>

    <div class="chart-container" ref="chartRef"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { TrendCharts } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { paperApi } from '@/api/paper'

const router = useRouter()
const loading = ref(true)
const chartRef = ref<HTMLElement | null>(null)
const chartInstance = shallowRef<echarts.ECharts | null>(null)

function initChart(data: any[]) {
  if (!chartRef.value) return
  
  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }
  
  const dates = data.map(d => d.date)
  
  // Extract PNL (Profit and Loss in percentage)
  // `NavPoint` interface has either `nav` or `net_value` and `profit_pct`
  const myPnl = data.map(d => {
    if (d.profit_pct !== undefined) return d.profit_pct
    if (d.nav !== undefined) return (d.nav - 1) * 100
    if (d.net_value !== undefined && d.initial_capital) return ((d.net_value - d.initial_capital) / d.initial_capital) * 100
    return 0.0
  })
  
  // Extract HS300 PNL (mock or real if available, assume hs300_nav starts at 1)
  const hs300Pnl = data.map(d => {
    const nav = d.hs300_nav || 1.0
    return (nav - 1) * 100
  })
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: function (params: any) {
        let res = `${params[0].name}<br/>`
        params.forEach((p: any) => {
          const color = p.seriesName === '我的策略' ? '#4f46e5' : 'var(--text-muted)'
          const val = p.value.toFixed(2)
          const sign = p.value >= 0 ? '+' : ''
          res += `<span style="display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:${color};"></span>`
          res += `${p.seriesName}: ${sign}${val}%<br/>`
        })
        return res
      }
    },
    legend: {
      data: ['我的策略', '沪深300'],
      bottom: 0,
      icon: 'circle',
      itemWidth: 8,
    },
    grid: {
      top: 20,
      left: 10,
      right: 15,
      bottom: 40, /* Increased from 30 to give more room for X-axis labels and legend */
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#e5e7eb' } },
      axisLabel: { 
        color: '#6b7280', 
        fontSize: 10,
        // If there are many dates, avoid overlapping
        hideOverlap: true,
        // Shorten the date format to MM-DD to save space
        formatter: (value: string) => {
          if (!value) return ''
          // If value is YYYY-MM-DD, return MM-DD
          const parts = value.split('-')
          return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : value
        }
      },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#6b7280',
        fontSize: 10,
        formatter: (val: number) => val.toFixed(0) + '%'
      },
      splitLine: {
        lineStyle: { type: 'dashed', color: '#f3f4f6' }
      }
    },
    series: [
      {
        name: '我的策略',
        type: 'line',
        data: myPnl,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 3, color: '#4f46e5' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(79, 70, 229, 0.2)' },
            { offset: 1, color: 'rgba(79, 70, 229, 0)' }
          ])
        }
      },
      {
        name: '沪深300',
        type: 'line',
        data: hs300Pnl,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: '#9ca3af', type: 'dashed' }
      }
    ]
  }
  
  chartInstance.value.setOption(option)
}

async function loadData() {
  loading.value = true
  try {
    // Fetch historical NAV for chart
    const res = await paperApi.getNav()
    const data = (res as any).data?.data || (res as any).data || res || []
    
    // If no real data, create mock data for demonstration
    if (data.length === 0) {
      const mockData = []
      let nav = 1.0
      let hs = 1.0
      const today = new Date()
      for (let i = 30; i >= 0; i--) {
        const d = new Date(today)
        d.setDate(d.getDate() - i)
        if (d.getDay() === 0 || d.getDay() === 6) continue
        
        nav = nav * (1 + (Math.random() * 0.04 - 0.015))
        hs = hs * (1 + (Math.random() * 0.03 - 0.015))
        
        mockData.push({
          date: d.toISOString().slice(0, 10),
          nav: nav,
          hs300_nav: hs
        })
      }
      initChart(mockData)
    } else {
      initChart(data)
    }
  } catch (err) {
    console.error('Failed to load NAV data', err)
  } finally {
    loading.value = false
  }
}

function handleResize() {
  chartInstance.value?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance.value?.dispose()
})
</script>

<style scoped>
.account-nav-widget {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.title .el-icon {
  color: var(--brand-500);
}

.live-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
  padding: 2px 8px;
  border-radius: 12px;
}

.pulse {
  width: 6px;
  height: 6px;
  background-color: var(--el-color-success);
  border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.7);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(103, 194, 58, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(103, 194, 58, 0); }
}

.modern-btn {
  color: var(--brand-500);
  font-weight: 500;
}

.chart-container {
  flex: 1;
  min-height: 250px;
  width: 100%;
}
</style>