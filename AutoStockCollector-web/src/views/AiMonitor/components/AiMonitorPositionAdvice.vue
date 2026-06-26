<template>
  <div class="pa-page">
    <!-- Stats -->
    <div class="pa-stats">
      <el-card shadow="never" class="pa-stat-card" v-for="s in statCards" :key="s.label" :class="s.cls">
        <div class="pa-stat-label">{{ s.label }}</div>
        <div class="pa-stat-value">{{ s.count }}</div>
      </el-card>
    </div>

    <!-- Filter -->
    <div class="pa-filter">
      <el-input v-model="searchText" placeholder="搜索股票代码/名称" clearable size="small" style="width: 200px;" />
      <el-select v-model="adviceFilter" placeholder="建议筛选" clearable size="small" style="width: 140px;">
        <el-option label="全部" value="" />
        <el-option label="买入" value="buy" />
        <el-option label="加仓" value="add" />
        <el-option label="减仓" value="reduce" />
        <el-option label="持有" value="hold" />
        <el-option label="卖出" value="sell" />
      </el-select>
    </div>

    <!-- Position Advice Cards -->
    <div class="pa-list" v-loading="loading">
      <el-card v-for="s in filtered" :key="s.code" shadow="never" class="pa-card" :class="'pa-' + (s.trading_advice?.action_signal || 'hold')">
        <div class="pa-card-header">
          <div class="pa-stock-info">
            <span class="pa-name">{{ s.name }}</span>
            <span class="pa-code">{{ s.code }}</span>
            <el-tag size="small" effect="plain" type="info">{{ s.type }}</el-tag>
          </div>
          <div class="pa-action-badge">
            <el-tag :type="adviceTagType(s.trading_advice?.action_signal || 'hold')" effect="dark" size="large" class="action-tag">
              {{ s.trading_advice?.action || '持有' }}
            </el-tag>
            <el-tag v-if="s.trading_advice?.signal_source" size="small" effect="plain" type="warning" class="source-tag">
              {{ signalSourceLabel(s.trading_advice.signal_source) }}
            </el-tag>
          </div>
        </div>

        <div class="pa-card-body">
          <div class="pa-metrics">
            <div class="pa-metric">
              <span class="pa-m-label">现价</span>
              <span class="pa-m-val">¥{{ s.price?.toFixed(2) }}</span>
            </div>
            <div class="pa-metric" v-if="s.price_prediction">
              <span class="pa-m-label">目标</span>
              <span class="pa-m-val up">¥{{ s.price_prediction.target_price?.toFixed(2) }}</span>
            </div>
            <div class="pa-metric" v-if="s.price_prediction">
              <span class="pa-m-label">止损</span>
              <span class="pa-m-val dn">¥{{ s.price_prediction.stop_loss?.toFixed(2) }}</span>
            </div>
            <div class="pa-metric" v-if="s.price_prediction">
              <span class="pa-m-label">预期收益</span>
              <span :class="['pa-m-val', s.price_prediction.expected_return > 0 ? 'up' : 'dn']">
                {{ s.price_prediction.expected_return > 0 ? '+' : '' }}{{ s.price_prediction.expected_return?.toFixed(1) }}%
              </span>
            </div>
            <div class="pa-metric">
              <span class="pa-m-label">盈亏</span>
              <span :class="['pa-m-val', s.change_rate > 0 ? 'up' : s.change_rate < 0 ? 'dn' : '']">
                {{ s.change_rate > 0 ? '+' : '' }}{{ s.change_rate?.toFixed(2) }}%
              </span>
            </div>
          </div>

          <div class="pa-reasons">
            <div v-for="(r, i) in (s.trading_advice?.reasons || s.trading_advice?.reason?.split(';') || [])" :key="i" class="pa-reason">
              <el-icon :size="12"><WarningFilled /></el-icon> {{ r }}
            </div>
          </div>

          <div class="pa-scores">
            <div class="pa-score-item" v-for="dim in scoreDims" :key="dim.key">
              <span class="pa-score-label">{{ dim.label }}</span>
              <el-progress :percentage="getScore(s, dim.key)" :stroke-width="6" :color="scoreColor(getScore(s, dim.key))" />
            </div>
          </div>

          <div class="pa-extras" v-if="s.concepts?.length">
            <el-tag v-for="c in s.concepts.slice(0, 4)" :key="c" size="small" effect="plain" class="concept-tag">{{ c }}</el-tag>
          </div>

          <div class="pa-footer" v-if="s.trading_advice?.advice?.summary">
            <el-icon><InfoFilled /></el-icon> {{ s.trading_advice.advice.summary }}
          </div>
        </div>
      </el-card>
      <el-empty v-if="!loading && filtered.length === 0" description="暂无持仓建议数据" :image-size="60" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { WarningFilled, InfoFilled } from '@element-plus/icons-vue'
import type { MonitorSignal } from '@/api/monitor'

const props = defineProps<{
  signals: MonitorSignal[]
  loading: boolean
}>()

const searchText = ref('')
const adviceFilter = ref('')

const positions = computed(() => props.signals.filter(s => s.type === '持仓'))

const statCards = computed(() => {
  const list = positions.value
  return [
    { label: '持仓总数', count: list.length, cls: 'sc-total' },
    { label: '建议买入', count: list.filter(s => s.trading_advice?.action_signal === 'buy').length, cls: 'sc-buy' },
    { label: '建议加仓', count: list.filter(s => s.trading_advice?.action_signal === 'add').length, cls: 'sc-add' },
    { label: '建议持有', count: list.filter(s => s.trading_advice?.action_signal === 'hold').length, cls: 'sc-hold' },
    { label: '建议减仓', count: list.filter(s => s.trading_advice?.action_signal === 'reduce').length, cls: 'sc-reduce' },
    { label: '建议卖出', count: list.filter(s => s.trading_advice?.action_signal === 'sell').length, cls: 'sc-sell' },
  ]
})

const filtered = computed(() => {
  let list = positions.value
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(s => s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
  }
  if (adviceFilter.value) {
    list = list.filter(s => s.trading_advice?.action_signal === adviceFilter.value)
  }
  return list
})

const scoreDims = [
  { key: 'fund_flow_score', label: '资金' },
  { key: 'research_score', label: '研报' },
  { key: 'technical_score', label: '技术' },
  { key: 'composite_score', label: '综合' },
]

function getScore(s: MonitorSignal, key: string): number {
  return s.trading_advice?.details?.[key] ?? 50
}

function adviceTagType(sig: string) {
  if (sig === 'buy') return 'danger'
  if (sig === 'add') return 'warning'
  if (sig === 'reduce') return 'info'
  if (sig === 'sell') return 'success'
  return ''
}

function signalSourceLabel(src: string) {
  const map: Record<string, string> = {
    '多维共振': '多维共振',
    '盈亏比+单维度': '盈亏比',
    '多维度共振': '共振',
    '板块轮动': '板块',
    '龙虎榜机构': '龙虎榜',
    '止盈': '止盈',
    '止损': '止损',
    '资金撤退': '资金撤退',
    '技术破位': '技术破位',
    '双弱': '双弱',
  }
  return map[src] || src
}

function scoreColor(v: number) {
  if (v >= 65) return '#F23645'
  if (v >= 50) return 'var(--el-color-warning)'
  if (v >= 35) return 'var(--text-muted)'
  return '#11C27E'
}
</script>

<style scoped>
.pa-page { display: flex; flex-direction: column; gap: 12px; }
.pa-stats { display: flex; gap: 10px; flex-wrap: wrap; }
.pa-stat-card { flex: 1; min-width: 90px; text-align: center; }
.pa-stat-label { font-size: 12px; color: var(--text-muted, #999); }
.pa-stat-value { font-size: 20px; font-weight: 700; }
.sc-total .pa-stat-value { color: var(--text-primary); }
.sc-buy .pa-stat-value { color: #F23645; }
.sc-add .pa-stat-value { color: var(--el-color-warning); }
.sc-hold .pa-stat-value { color: #409eff; }
.sc-reduce .pa-stat-value { color: var(--text-muted); }
.sc-sell .pa-stat-value { color: #11C27E; }

.pa-filter { display: flex; gap: 8px; }
.pa-list { display: flex; flex-direction: column; gap: 10px; }
.pa-card { border-left: 4px solid #dcdfe6; border-radius: 8px; }
.pa-buy { border-left-color: #F23645; }
.pa-add { border-left-color: var(--el-color-warning); }
.pa-hold { border-left-color: #409eff; }
.pa-reduce { border-left-color: var(--text-muted); }
.pa-sell { border-left-color: #11C27E; }

.pa-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pa-stock-info { display: flex; align-items: center; gap: 6px; }
.pa-name { font-weight: 600; font-size: 15px; }
.pa-code { font-size: 11px; color: var(--text-faint, #bbb); font-family: var(--font-mono); }
.pa-action-badge { display: flex; align-items: center; gap: 6px; }
.action-tag { font-size: 14px; font-weight: 700; padding: 6px 14px; }
.source-tag { font-size: 11px; }

.pa-metrics { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }
.pa-metric { flex: 1; min-width: 80px; }
.pa-m-label { font-size: 11px; color: var(--text-muted, #999); display: block; }
.pa-m-val { font-size: 14px; font-weight: 600; font-family: var(--font-mono); }
.up { color: #F23645; }
.dn { color: #11C27E; }

.pa-reasons { margin-bottom: 8px; }
.pa-reason { font-size: 12px; color: var(--text-secondary); line-height: 1.6; }
.pa-scores { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.pa-score-item { flex: 1; min-width: 100px; }
.pa-score-label { font-size: 11px; color: var(--text-muted, #999); display: block; margin-bottom: 2px; }

.pa-extras { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
.concept-tag { font-size: 11px; }

.pa-footer { font-size: 12px; color: var(--text-primary); background: var(--bg-soft, #f5f7fa); padding: 6px 10px; border-radius: 4px; display: flex; align-items: center; gap: 4px; }
</style>
