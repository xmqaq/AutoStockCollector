<template>
  <div class="strategy-back">
    <el-row :gutter="16">
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
            <el-form-item label="风控配置">
              <el-row :gutter="8">
                <el-col :span="12">
                  <el-input-number
                    v-model="form.stop_loss"
                    :min="1"
                    :max="50"
                    :step="1"
                    controls-position="right"
                    placeholder="止损%"
                  />
                </el-col>
                <el-col :span="12">
                  <el-input-number
                    v-model="form.take_profit"
                    :min="1"
                    :max="100"
                    :step="1"
                    controls-position="right"
                    placeholder="止盈%"
                  />
                </el-col>
              </el-row>
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

        <el-card v-if="result" shadow="never" class="section-card config-summary">
          <template #header><span>配置摘要</span></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="策略">{{ form.strategy }}</el-descriptions-item>
            <el-descriptions-item label="日期范围">
              {{ dateRange ? `${dateRange[0]} ~ ${dateRange[1]}` : '--' }}
            </el-descriptions-item>
            <el-descriptions-item label="止损/止盈">
              {{ form.stop_loss }}% / {{ form.take_profit }}%
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card v-if="!result && !loading" shadow="never" class="section-card empty-hint-card">
          <div class="empty-hint-inner">
            <div class="empty-hint-icon">&#9654;</div>
            <div class="empty-hint-title">策略回测</div>
            <ul class="empty-hint-steps">
              <li>在左侧选择回测策略</li>
              <li>输入要回测的股票代码（可多只）</li>
              <li>设置回测时间范围与初始资金</li>
              <li>点击「开始回测」查看收益分析</li>
            </ul>
            <div class="empty-hint-note">回测基于历史K线数据，不代表未来实际收益</div>
          </div>
        </el-card>

        <template v-if="result">
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
                <div class="metric-label">年化收益率</div>
                <div :class="['metric-value', (result.annualized_return as number) >= 0 ? 'text-rise' : 'text-fall']">
                  {{ fmtChange((result.annualized_return as number) || 0) }}
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
            <el-col :span="6">
              <el-card class="metric-card" shadow="never">
                <div class="metric-label">索提诺比率</div>
                <div class="metric-value text-primary">
                  {{ fmtNumber((result.sortino_ratio as number) || 0) }}
                </div>
              </el-card>
            </el-col>
          </el-row>

          <el-row :gutter="12" class="result-metrics" style="margin-top:12px">
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
                <div class="metric-label">盈亏比</div>
                <div class="metric-value">
                  {{ ((result.profit_loss_ratio as number) || 0).toFixed(2) }}
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="metric-card" shadow="never">
                <div class="metric-label">总交易次数</div>
                <div class="metric-value">
                  {{ result.total_trades || 0 }}
                </div>
              </el-card>
            </el-col>
          </el-row>

          <el-card shadow="never" class="section-card" style="margin-top:12px" v-loading="loading">
            <template #header><span>收益曲线</span></template>
            <div v-if="equityCurve.length > 0">
              <v-chart :option="lineOption" style="height:300px" autoresize />
            </div>
            <el-empty v-else description="暂无收益曲线数据" :image-size="60" />
          </el-card>

          <el-card shadow="never" class="section-card" style="margin-top:12px">
            <template #header><span>交易统计</span></template>
            <el-descriptions :column="3" border size="small">
              <el-descriptions-item label="盈利交易">
                <span class="text-rise">{{ result.winning_trades || 0 }}笔</span>
              </el-descriptions-item>
              <el-descriptions-item label="亏损交易">
                <span class="text-fall">{{ result.losing_trades || 0 }}笔</span>
              </el-descriptions-item>
              <el-descriptions-item label="平均持仓天数">
                {{ ((result.avg_holding_days as number) || 0).toFixed(1) }}天
              </el-descriptions-item>
              <el-descriptions-item label="初始资金">
                {{ fmtAmount(form.initial_cash) }}
              </el-descriptions-item>
              <el-descriptions-item label="最终资金">
                {{ fmtAmount((result.final_value as number) || form.initial_cash) }}
              </el-descriptions-item>
              <el-descriptions-item label="总盈亏">
                <span :class="((result.final_value as number || 0) >= form.initial_cash ? 'text-rise' : 'text-fall')">
                  {{ fmtChange((result.total_return as number) || 0) }}
                </span>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card v-if="(result.sample_trades?.length || 0) > 0" shadow="never" class="section-card" style="margin-top:12px">
            <template #header><span>交易明细 (前20笔)</span></template>
            <el-table :data="result.sample_trades" stripe size="small">
              <el-table-column prop="date" label="日期" width="110" />
              <el-table-column prop="code" label="代码" width="100">
                <template #default="{ row }">
                  <router-link :to="`/stock-detail?code=${row.code}`" class="trade-link">
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
              <el-table-column prop="price" label="价格" width="90">
                <template #default="{ row }">
                  {{ row.price?.toFixed(2) }}
                </template>
              </el-table-column>
              <el-table-column prop="shares" label="数量" width="80" />
              <el-table-column prop="pnl" label="盈亏" width="90">
                <template #default="{ row }">
                  <span :class="row.pnl >= 0 ? 'text-rise' : 'text-fall'">
                    {{ (row.pnl || 0).toFixed(2) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="pnl_percent" label="收益率" width="80">
                <template #default="{ row }">
                  <span :class="row.pnl_percent >= 0 ? 'text-rise' : 'text-fall'">
                    {{ (row.pnl_percent || 0).toFixed(2) }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="reason" label="原因" width="100" show-overflow-tooltip />
              <el-table-column prop="holding_days" label="持仓天数" width="90" />
            </el-table>
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
const result = ref<BacktestReport | null>(null)
const codesInput = ref('SH600000, SZ000001')
const dateRange = ref<[string, string]>([
  dayjs().subtract(1, 'year').format('YYYY-MM-DD'),
  dayjs().format('YYYY-MM-DD'),
])

interface BacktestReport {
  total_return?: number
  annual_return?: number
  max_drawdown?: number
  win_rate?: number
  sharpe_ratio?: number
  final_value?: number
  equity_curve?: { date: string; value: number }[]
  sample_trades?: {
    date: string
    code: string
    type: string
    price: number
    amount: number
    pnl?: number
  }[]
  [key: string]: unknown
}

const form = ref({
  strategy: '',
  initial_cash: 1000000,
  stop_loss: 5,
  take_profit: 10,
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
  const startVal = values[0] || 0
  const colors = values.map(v => v >= startVal ? RISE_COLOR : '#26a69a')

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
      stop_loss: form.value.stop_loss / 100,
      take_profit: form.value.take_profit / 100,
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

.config-summary {
  margin-top: 12px;
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

.empty-hint-card {
  min-height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-hint-card :deep(.el-card__body) {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 32px;
}

.empty-hint-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.empty-hint-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(64,158,255,0.12);
  color: #409eff;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-left: 4px;
}

.empty-hint-title {
  font-size: 16px;
  font-weight: 600;
  color: #c8cdd6;
}

.empty-hint-steps {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  counter-reset: step;
}

.empty-hint-steps li {
  counter-increment: step;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #909399;
}

.empty-hint-steps li::before {
  content: counter(step);
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #2c2c2c;
  color: #409eff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.empty-hint-note {
  font-size: 11px;
  color: #606266;
  margin-top: 4px;
  border-top: 1px solid #2c2c2c;
  padding-top: 12px;
  width: 100%;
}

.trade-link {
  color: #409eff;
  text-decoration: none;
}

.trade-link:hover {
  text-decoration: underline;
}
</style>
