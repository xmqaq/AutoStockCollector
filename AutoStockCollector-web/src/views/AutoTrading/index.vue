<template>
  <div class="auto-trading">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="交易仪表盘" name="main">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-card shadow="never">
              <div class="stat-label">账户现金</div>
              <div class="stat-value">{{ fmt(account_cash) }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never">
              <div class="stat-label">持仓市值</div>
              <div class="stat-value">{{ fmt(total_market_value) }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never">
              <div class="stat-label">总盈亏</div>
              <div :class="['stat-value', total_pnl >= 0 ? 'up' : 'down']">
                {{ fmt(total_pnl) }} ({{ total_pnl_pct }}%)
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="never">
              <div class="stat-label">持仓/上限</div>
              <div class="stat-value">{{ position_count }}/{{ max_positions }}</div>
              <el-progress :percentage="exposure_pct" :stroke-width="6" :color="exposureColor" />
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top:16px">
          <el-col :span="12">
            <el-card shadow="never">
              <template #header>
                <div class="card-header"><span>持仓信号</span><el-button size="small" type="primary" @click="loadSignals">刷新</el-button></div>
              </template>
              <el-table :data="signals" size="small" stripe max-height="420">
                <el-table-column prop="code" label="代码" width="90" />
                <el-table-column prop="name" label="名称" width="80" />
                <el-table-column label="综合评分" width="90">
                  <template #default="{ row }"><el-tag :type="scoreTagType(row.overall_score)" size="small">{{ row.overall_score }}</el-tag></template>
                </el-table-column>
                <el-table-column label="信号" width="90">
                  <template #default="{ row }"><el-tag :type="signalTagType(row.signal)" size="small">{{ signalLabel(row.signal) }}</el-tag></template>
                </el-table-column>
                <el-table-column prop="breakdown.auction_score" label="竞价" width="60" align="center" />
                <el-table-column prop="breakdown.pa_signal" label="PA" width="80" align="center" />
                <el-table-column prop="breakdown.ai_score" label="AI" width="60" align="center" />
                <el-table-column label="理由" min-width="140">
                  <template #default="{ row }"><el-tooltip :content="row.reasons.join('; ')" placement="top"><span class="reasons-text">{{ row.reasons.join('; ') || '-' }}</span></el-tooltip></template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never">
              <template #header>
                <div class="card-header">
                  <span>持仓明细</span>
                  <div>
                    <el-button size="small" type="danger" plain @click="handleCloseAll">一键平仓</el-button>
                    <el-button size="small" type="warning" plain @click="handleCycle">执行轮询</el-button>
                  </div>
                </div>
              </template>
              <el-table :data="positions" size="small" stripe max-height="420">
                <el-table-column prop="code" label="代码" width="90" />
                <el-table-column prop="name" label="名称" width="70" />
                <el-table-column prop="shares" label="持股" width="70" align="right" />
                <el-table-column label="均价" width="80" align="right"><template #default="{ row }">{{ row.avg_cost.toFixed(2) }}</template></el-table-column>
                <el-table-column label="现价" width="80" align="right"><template #default="{ row }">{{ row.current_price.toFixed(2) }}</template></el-table-column>
                <el-table-column label="盈亏%" width="80" align="right">
                  <template #default="{ row }"><span :class="row.pnl_percent >= 0 ? 'up' : 'down'">{{ row.pnl_percent.toFixed(2) }}</span></template>
                </el-table-column>
                <el-table-column label="止损" width="80" align="right"><template #default="{ row }">{{ row.stop_loss?.toFixed(2) ?? '-' }}</template></el-table-column>
                <el-table-column label="止盈" width="80" align="right"><template #default="{ row }">{{ row.take_profit?.toFixed(2) ?? '-' }}</template></el-table-column>
              </el-table>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="16" style="margin-top:16px">
          <el-col :span="24">
            <el-card shadow="never">
              <template #header><div class="card-header"><span>执行历史</span></div></template>
              <el-table :data="history" size="small" stripe max-height="300">
                <el-table-column label="时间" width="170"><template #default="{ row }">{{ row.cycle_time?.slice(0, 19) ?? '-' }}</template></el-table-column>
                <el-table-column prop="buys" label="买入" width="60" align="center" />
                <el-table-column prop="sells" label="卖出" width="60" align="center" />
                <el-table-column prop="adds" label="加仓" width="60" align="center" />
                <el-table-column prop="reduces" label="减仓" width="60" align="center" />
                <el-table-column prop="errors" label="错误" width="60" align="center" />
                <el-table-column label="详情" min-width="200">
                  <template #default="{ row }"><span class="reasons-text">{{ row.details?.slice(0, 5).map((d: any) => `${d.action} ${d.code} × ${d.shares}`).join(', ') ?? '-' }}</span></template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="回撤策略" name="drawdown">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>自动回撤策略</span>
              <el-button size="small" type="primary" :loading="saving" @click="handleSaveDrawdown">保存</el-button>
            </div>
          </template>
          <el-form label-width="180px" style="max-width:600px">
            <el-form-item label="启用回撤策略">
              <el-switch v-model="dd.enabled" />
            </el-form-item>
            <el-form-item label="追踪回撤触发(%)">
              <el-slider v-model="dd.trailing_stop_pct" :min="1" :max="20" :step="0.5" show-input />
            </el-form-item>
            <el-form-item label="触发时操作">
              <el-radio-group v-model="dd.trailing_action">
                <el-radio value="sell">全数卖出</el-radio>
                <el-radio value="reduce">减半持仓</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="减仓比例" v-if="dd.trailing_action === 'reduce'">
              <el-slider v-model="dd.reduce_ratio" :min="0.1" :max="0.9" :step="0.1" show-input />
            </el-form-item>
            <el-form-item label="利润锁定">
              <el-switch v-model="dd.profit_lock_enabled" />
            </el-form-item>
            <el-form-item label="锁定阈值(%)" v-if="dd.profit_lock_enabled">
              <el-slider v-model="dd.profit_lock_threshold" :min="0.5" :max="10" :step="0.5" show-input />
              <div class="form-help">盈利超过此值后追踪回撤才生效，避免微利时被震出</div>
            </el-form-item>
            <el-form-item label="最大回撤止损(%)">
              <el-slider v-model="dd.max_drawdown_pct" :min="5" :max="30" :step="1" show-input />
              <div class="form-help">从持仓最高点回落超过此比例 → 无条件卖出（硬止损）</div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { autoTradingApi, type FusedSignalItem, type CycleResult } from '@/api/autoTrading'

const activeTab = ref('main')
const account_cash = ref(0)
const total_market_value = ref(0)
const total_pnl = ref(0)
const total_pnl_pct = ref(0)
const position_count = ref(0)
const max_positions = ref(8)
const exposure_pct = ref(0)
const positions = ref<any[]>([])
const signals = ref<FusedSignalItem[]>([])
const history = ref<CycleResult[]>([])
const saving = ref(false)

import type { DrawdownStrategyConfig } from '@/api/autoTrading'

const dd = ref<DrawdownStrategyConfig>({
  enabled: false,
  trailing_stop_pct: 5,
  trailing_action: 'sell',
  reduce_ratio: 0.5,
  profit_lock_enabled: true,
  profit_lock_threshold: 3,
  max_drawdown_pct: 15,
})

function fmt(v: number) { return `¥${v.toFixed(2)}` }

function scoreTagType(s: number) { return s >= 75 ? 'success' : s >= 55 ? 'warning' : 'danger' }
function signalTagType(s: string) { return s === 'strong_buy' || s === 'buy' ? 'success' : s === 'sell' || s === 'strong_sell' ? 'danger' : 'info' }
function signalLabel(s: string) { return ({ strong_buy: '强力买入', buy: '买入', hold: '持有', sell: '卖出', strong_sell: '强力卖出', reduce: '减仓' })[s] || s }
function exposureColor(p: number) { return p > 80 ? '#f56c6c' : p > 60 ? '#e6a23c' : '#67c23a' }

async function loadStatus() {
  const r = await autoTradingApi.getStatus()
  if (!r.data?.success) return
  const d = r.data.data!
  account_cash.value = d.account_cash
  total_market_value.value = d.total_market_value
  total_pnl.value = d.total_pnl
  total_pnl_pct.value = d.total_pnl_pct
  position_count.value = d.position_count
  max_positions.value = d.max_positions
  exposure_pct.value = d.exposure_pct
  positions.value = d.positions || []
}

async function loadSignals() {
  const r = await autoTradingApi.getSignals()
  if (!r.data?.success) return
  signals.value = r.data.data?.signals || []
}

async function loadHistory() {
  const r = await autoTradingApi.getHistory(20)
  if (!r.data?.success) return
  history.value = r.data.data || []
}

async function loadDrawdown() {
  const r = await autoTradingApi.getDrawdownStrategy()
  if (!r.data?.success) return
  Object.assign(dd.value, r.data.data)
}

async function handleCycle() {
  const r = await autoTradingApi.triggerCycle()
  if (!r.data?.success) { ElMessage.warning(r.data?.error || '轮询失败'); return }
  ElMessage.success(`轮询完成: ${r.data.data?.buys}买 ${r.data.data?.sells}卖`)
  loadStatus(); loadSignals(); loadHistory()
}

async function handleCloseAll() {
  try { await ElMessageBox.confirm('确定一键平仓所有持仓？', '确认', { type: 'warning' }) } catch { return }
  const r = await autoTradingApi.closeAllPositions()
  if (!r.data?.success) { ElMessage.warning(r.data?.error || '平仓失败'); return }
  ElMessage.success(`已平仓 ${r.data.data?.closed} 笔`); loadStatus()
}

async function handleSaveDrawdown() {
  saving.value = true
  try {
    const r = await autoTradingApi.saveDrawdownStrategy(dd.value)
    if (!r.data?.success) { ElMessage.warning(r.data?.error || '保存失败'); return }
    Object.assign(dd.value, r.data.data)
    ElMessage.success('回撤策略已保存')
  } finally { saving.value = false }
}

onMounted(() => { loadStatus(); loadSignals(); loadHistory(); loadDrawdown() })
</script>

<style scoped>
.auto-trading { padding: 16px; }
.stat-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.stat-value { font-size: 22px; font-weight: 600; }
.stat-value.up { color: #f56c6c; }
.stat-value.down { color: #67c23a; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.reasons-text { font-size: 12px; color: #606266; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-block; max-width: 100%; }
.form-help { font-size: 12px; color: #909399; margin-top: 4px; }
</style>
