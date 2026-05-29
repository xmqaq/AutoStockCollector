<template>
  <div class="backtest-visualizer">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>回测可视化分析</span>
          <el-radio-group v-model="timeRange" size="small">
            <el-radio-button label="1M">近1月</el-radio-button>
            <el-radio-button label="3M">近3月</el-radio-button>
            <el-radio-button label="6M">近6月</el-radio-button>
            <el-radio-button label="ALL">全部</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon rise">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.totalReturn }}</div>
            <div class="stat-label">总收益率</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon warning">
            <el-icon><Bottom /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.maxDrawdown }}</div>
            <div class="stat-label">最大回撤</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon info">
            <el-icon><Odometer /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.sharpeRatio }}</div>
            <div class="stat-label">夏普比率</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon success">
            <el-icon><CircleCheck /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.winRate }}</div>
            <div class="stat-label">胜率</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">
            <el-icon><DataLine /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.totalTrades }}</div>
            <div class="stat-label">总交易次数</div>
          </div>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="section-card">
      <template #header>
        <span>Equity曲线</span>
      </template>
      <v-chart :option="equityOption" style="height: 300px" autoresize />
    </el-card>
    
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>交易记录</span>
          <el-select v-model="tradeFilter" size="small" style="width: 120px">
            <el-option label="全部" value="all" />
            <el-option label="买入" value="buy" />
            <el-option label="卖出" value="sell" />
          </el-select>
        </div>
      </template>
      
      <el-table :data="filteredTrades" stripe size="small" max-height="300">
        <el-table-column prop="date" label="日期" width="100" />
        <el-table-column prop="code" label="代码" width="100">
          <template #default="{ row }">
            <router-link :to="`/stock-detail?code=${row.code}`" class="stock-link">
              {{ row.code }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="方向" width="70">
          <template #default="{ row }">
            <el-tag :type="row.type === 'buy' ? 'success' : 'danger'" size="small">
              {{ row.type === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="80" align="right">
          <template #default="{ row }">{{ row.price?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="数量" width="80" align="right" />
        <el-table-column prop="pnl" label="盈亏" width="90" align="right">
          <template #default="{ row }">
            <span :class="row.pnl >= 0 ? 'text-rise' : 'text-fall'">
              {{ row.pnl >= 0 ? '+' : '' }}{{ (row.pnl || 0).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" />
      </el-table>
    </el-card>
    
    <el-card shadow="never" class="section-card">
      <template #header>
        <span>月度收益分布</span>
      </template>
      <v-chart :option="monthlyOption" style="height: 250px" autoresize />
    </el-card>
    
    <el-card shadow="never" class="section-card">
      <template #header>
        <span>交易胜率分析</span>
      </template>
      <div class="win-rate-grid">
        <div class="win-rate-chart">
          <v-chart :option="winRatePieOption" style="height: 200px" autoresize />
        </div>
        <div class="win-rate-details">
          <div class="detail-item">
            <span class="detail-label">盈利次数</span>
            <span class="detail-value rise">{{ winStats.winning }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">亏损次数</span>
            <span class="detail-value fall">{{ winStats.losing }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">平均盈利</span>
            <span class="detail-value rise">{{ winStats.avgProfit }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">平均亏损</span>
            <span class="detail-value fall">{{ winStats.avgLoss }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">盈亏比</span>
            <span class="detail-value">{{ winStats.profitLossRatio }}</span>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart, PieChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { TrendCharts, Bottom, Odometer, CircleCheck, DataLine } from '@element-plus/icons-vue'

use([LineChart, PieChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

interface Trade {
  date: string
  code: string
  type: 'buy' | 'sell'
  price: number
  amount: number
  pnl?: number
  reason?: string
}

interface BacktestData {
  equityCurve?: { date: string; value: number }[]
  trades?: Trade[]
}

const props = withDefaults(defineProps<{
  data?: BacktestData
}>(), {
  data: () => ({ equityCurve: [], trades: [] }),
})

const timeRange = ref('3M')
const tradeFilter = ref('all')

const stats = computed(() => ({
  totalReturn: '+18.5%',
  maxDrawdown: '-5.2%',
  sharpeRatio: '1.85',
  winRate: '65%',
  totalTrades: '24',
}))

const mockEquityCurve = computed(() => {
  const result = []
  let value = 100000
  for (let i = 0; i < 90; i++) {
    const date = new Date()
    date.setDate(date.getDate() - (90 - i))
    value += (Math.random() - 0.45) * 2000
    result.push({
      date: date.toISOString().split('T')[0],
      value: Math.round(value * 100) / 100,
    })
  }
  return result
})

const mockTrades = computed<Trade[]>(() => [
  { date: '2024-01-15', code: 'SH600000', type: 'buy', price: 12.50, amount: 1000, pnl: 500, reason: '技术金叉' },
  { date: '2024-01-22', code: 'SH600000', type: 'sell', price: 13.00, amount: 1000, pnl: 500, reason: '止盈' },
  { date: '2024-02-05', code: 'SZ000001', type: 'buy', price: 10.20, amount: 2000, pnl: -200, reason: 'RSI超买' },
  { date: '2024-02-12', code: 'SZ000001', type: 'sell', price: 10.10, amount: 2000, pnl: -200, reason: '止损' },
  { date: '2024-02-20', code: 'SH600519', type: 'buy', price: 1680, amount: 100, pnl: 1500, reason: '资金流入' },
])

const filteredTrades = computed(() => {
  if (tradeFilter.value === 'all') return mockTrades.value
  return mockTrades.value.filter(t => t.type === tradeFilter.value)
})

const equityOption = computed(() => {
  const data = mockEquityCurve.value
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#2c2c2c',
      borderColor: '#444',
      textStyle: { color: '#e5eaf3' },
    },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date),
      axisLine: { lineStyle: { color: '#444' } },
      axisLabel: { color: '#909399', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#444' } },
      splitLine: { lineStyle: { color: '#2c2c2c', type: 'dashed' } },
      axisLabel: { color: '#909399', formatter: (v: number) => (v / 10000).toFixed(0) + '万' },
    },
    series: [{
      type: 'line',
      data: data.map(d => d.value),
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2, color: '#409eff' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(64,158,255,0.3)' },
            { offset: 1, color: 'rgba(64,158,255,0)' },
          ],
        },
      },
    }],
  }
})

const monthlyOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#2c2c2c',
    borderColor: '#444',
    textStyle: { color: '#e5eaf3' },
  },
  grid: { left: 50, right: 20, top: 20, bottom: 30 },
  xAxis: {
    type: 'category',
    data: ['1月', '2月', '3月', '4月', '5月', '6月'],
    axisLine: { lineStyle: { color: '#444' } },
    axisLabel: { color: '#909399' },
  },
  yAxis: {
    type: 'value',
    axisLine: { lineStyle: { color: '#444' } },
    splitLine: { lineStyle: { color: '#2c2c2c', type: 'dashed' } },
    axisLabel: { color: '#909399', formatter: (v: number) => v + '%' },
  },
  series: [{
    type: 'bar',
    data: [2.5, -1.2, 3.8, 1.5, -0.8, 4.2].map(v => ({
      value: v,
      itemStyle: { color: v >= 0 ? '#67c23a' : '#f56c6c' },
    })),
  }],
}))

const winRatePieOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'item', backgroundColor: '#2c2c2c', borderColor: '#444', textStyle: { color: '#e5eaf3' } },
  legend: { bottom: 0, textStyle: { color: '#909399' } },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: [
      { value: 65, name: '盈利', itemStyle: { color: '#67c23a' } },
      { value: 35, name: '亏损', itemStyle: { color: '#f56c6c' } },
    ],
    label: { color: '#e5eaf3' },
  }],
}))

const winStats = computed(() => ({
  winning: 15,
  losing: 8,
  avgProfit: '+2.5%',
  avgLoss: '-1.2%',
  profitLossRatio: '2.08',
}))

onMounted(() => {
  // Load data if needed
})
</script>

<style scoped>
.backtest-visualizer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-row {
  display: flex;
  gap: 12px;
}

.stat-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #2c2c2c;
  border-radius: 8px;
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #3c3c3c;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #909399;
}

.stat-icon.rise { background: rgba(239, 83, 80, 0.2); color: #ef5350; }
.stat-icon.warning { background: rgba(230, 162, 60, 0.2); color: #e6a23c; }
.stat-icon.success { background: rgba(103, 194, 58, 0.2); color: #67c23a; }
.stat-icon.info { background: rgba(64, 158, 255, 0.2); color: #409eff; }

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #e5eaf3;
}

.stat-label {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.stock-link {
  color: #409eff;
  text-decoration: none;
}

.stock-link:hover {
  text-decoration: underline;
}

.text-rise { color: #ef5350; }
.text-fall { color: #26a69a; }

.win-rate-grid {
  display: flex;
  gap: 24px;
}

.win-rate-chart {
  flex: 1;
}

.win-rate-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  justify-content: center;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #2c2c2c;
  border-radius: 4px;
}

.detail-label {
  font-size: 13px;
  color: #909399;
}

.detail-value {
  font-size: 14px;
  font-weight: 600;
  color: #e5eaf3;
}

.detail-value.rise { color: #67c23a; }
.detail-value.fall { color: #f56c6c; }

.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c;
  padding: 12px 16px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}
</style>