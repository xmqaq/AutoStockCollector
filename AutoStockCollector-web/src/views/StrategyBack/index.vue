<template>
  <div class="strategy-back">
    <el-row :gutter="16">
      <!-- Config panel -->
      <el-col :span="8">
        <el-card shadow="never" class="section-card">
          <template #header><span>回测配置</span></template>
          <el-form :model="form" label-width="90px" size="small">
            <el-form-item label="策略选择">
              <el-select v-model="form.strategy" style="width:100%" :loading="strategiesLoading">
                <el-option
                  v-for="s in strategies"
                  :key="s.name"
                  :label="s.name"
                  :value="s.name"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="股票代码">
              <el-input
                v-model="codesInput"
                type="textarea"
                :rows="3"
                placeholder="输入股票代码，逗号或换行分隔&#10;如: SH600000, SZ000001"
              />
            </el-form-item>
            <el-form-item label="日期范围">
              <el-date-picker
                v-model="dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始"
                end-placeholder="结束"
                format="YYYY年MM月DD日"
                value-format="YYYY-MM-DD"
                style="width:100%"
              />
            </el-form-item>
            <el-form-item label="初始资金">
              <el-input-number
                v-model="form.initial_cash"
                :min="10000"
                :step="10000"
                style="width:100%"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                @click="runBacktest"
                :loading="loading"
                style="width:100%"
              >
                开始回测
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- Results panel -->
      <el-col :span="16">
        <div v-if="!result && !loading" class="empty-hint">
          <el-empty description="配置参数后点击开始回测" />
        </div>

        <template v-if="result">
          <!-- Metric cards -->
          <el-row :gutter="12" class="result-metrics">
            <el-col :span="6">
              <el-card class="metric-card" shadow="never">
                <div class="metric-label">总收益率</div>
                <div :class="['metric-value', (result.total_return as number) >= 0 ? 'text-rise' : 'text-fall']">
                  {{ fmtChange((result.total_return as number) || 0) }}
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="metric-card" shadow="never">
                <div class="metric-label">最大回撤</div>
                <div class="metric-value text-fall">
                  {{ fmtChange((result.max_drawdown as number) || 0) }}
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="metric-card" shadow="never">
                <div class="metric-label">胜率</div>
                <div class="metric-value text-primary">
                  {{ fmtPercent((result.win_rate as number) || 0) }}
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="metric-card" shadow="never">
                <div class="metric-label">夏普比率</div>
                <div class="metric-value text-primary">
                  {{ fmtNumber((result.sharpe_ratio as number) || 0) }}
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- Equity curve chart -->
          <el-card shadow="never" class="section-card" style="margin-top:12px" v-loading="loading">
            <template #header><span>收益曲线</span></template>
            <div v-if="equityCurve.length > 0">
              <v-chart :option="lineOption" style="height:300px" autoresize />
            </div>
            <el-empty v-else description="暂无收益曲线数据" :image-size="60" />
          </el-card>

          <!-- Additional stats -->
          <el-card shadow="never" class="section-card" style="margin-top:12px">
            <template #header><span>详细统计</span></template>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="年化收益率">
                {{ fmtChange((result.annual_return as number) || 0) }}
              </el-descriptions-item>
              <el-descriptions-item label="初始资金">
                {{ fmtAmount(form.initial_cash) }}
              </el-descriptions-item>
              <el-descriptions-item label="策略">{{ form.strategy }}</el-descriptions-item>
              <el-descriptions-item label="日期范围">
                {{ dateRange ? `${dateRange[0]} ~ ${dateRange[1]}` : '--' }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </template>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { strategyApi } from '@/api/strategy'
import { backtestApi } from '@/api/backtest'
import { fmtAmount, fmtChange, fmtNumber, fmtPercent, RISE_COLOR } from '@/utils/format'
import { normalizeCode } from '@/utils/stockCode'
import type { StrategyItem } from '@/types'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, CanvasRenderer])

const loading = ref(false)
const strategiesLoading = ref(false)
const strategies = ref<StrategyItem[]>([])
const result = ref<Record<string, unknown> | null>(null)
const codesInput = ref('SH600000, SZ000001')
const dateRange = ref<[string, string]>([
  dayjs().subtract(1, 'year').format('YYYY-MM-DD'),
  dayjs().format('YYYY-MM-DD'),
])

const form = ref({
  strategy: '',
  initial_cash: 1000000,
})

const equityCurve = computed(() => {
  if (!result.value?.equity_curve) return []
  return result.value.equity_curve as { date: string; value: number }[]
})

const lineOption = computed(() => {
  const curve = equityCurve.value
  if (!curve.length) return {}
  const dates = curve.map(d => d.date)
  const values = curve.map(d => d.value)
  return {
    backgroundColor: '#1f1f1f',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#2c2c2c',
      borderColor: '#444',
      textStyle: { color: '#e5eaf3' },
    },
    grid: { left: 80, right: 20, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#909399', fontSize: 11, rotate: 30 },
      axisLine: { lineStyle: { color: '#444' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#909399',
        formatter: (v: number) => fmtAmount(v),
      },
      splitLine: { lineStyle: { color: '#2c2c2c' } },
    },
    series: [
      {
        name: '资产净值',
        type: 'line',
        data: values,
        smooth: true,
        lineStyle: { color: RISE_COLOR, width: 2 },
        areaStyle: { color: `${RISE_COLOR}20` },
        showSymbol: false,
        markLine: {
          data: [
            { type: 'average', name: '平均', lineStyle: { color: '#909399', type: 'dashed' } },
          ],
        },
      },
    ],
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', bottom: 8, height: 20 },
    ],
  }
})

async function loadStrategies() {
  strategiesLoading.value = true
  try {
    const res = await strategyApi.getStrategyList()
    strategies.value = res.data?.strategies || res.data?.data || res.data || []
    if (strategies.value.length > 0) {
      form.value.strategy = strategies.value[0].name
    }
  } catch {
    strategies.value = []
  } finally {
    strategiesLoading.value = false
  }
}

async function runBacktest() {
  if (!form.value.strategy) {
    ElMessage.warning('请选择策略')
    return
  }
  if (!dateRange.value) {
    ElMessage.warning('请选择日期范围')
    return
  }

  const rawCodes = codesInput.value.split(/[,\n]/).map(s => s.trim()).filter(Boolean)
  if (rawCodes.length === 0) {
    ElMessage.warning('请输入至少一个股票代码')
    return
  }
  const codes = rawCodes.map(normalizeCode)

  loading.value = true
  try {
    const res = await backtestApi.runBacktest({
      strategy: form.value.strategy,
      codes,
      start_date: dateRange.value[0],
      end_date: dateRange.value[1],
      initial_cash: form.value.initial_cash,
    })
    result.value = res.data?.report || res.data?.data || res.data || {}
  } catch {
    result.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStrategies()
})
</script>

<style scoped>
.strategy-back {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

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

.result-metrics {
  margin-bottom: 0;
}

.metric-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
  text-align: center;
  padding: 12px;
}

.metric-card :deep(.el-card__body) {
  padding: 16px 12px;
}

.metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
}

.text-rise { color: #ef5350; }
.text-fall { color: #26a69a; }
.text-primary { color: #409eff; }

.empty-hint {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}
</style>
