<template>
  <div class="signal-grid" v-loading="loading">
    <el-row :gutter="12">
      <el-col v-for="s in filteredSignals" :key="s.code" :xs="24" :sm="12" :lg="8" :xl="6">
        <el-card shadow="hover" class="signal-card" @click="$emit('show-detail', s)">
          <!-- Card Header -->
          <div class="card-header">
            <div class="card-title">
              <span class="stock-code">{{ s.code }}</span>
              <span class="stock-name">{{ s.name }}</span>
            </div>
            <el-tag :type="s.type === '持仓' ? 'warning' : 'info'" size="small" effect="plain">
              {{ s.type }}
            </el-tag>
          </div>

          <!-- Price -->
          <div class="card-price">
            <span class="price-val">{{ fmtPrice(s.price) }}</span>
            <span :class="['change', s.change_rate >= 0 ? 'up' : 'down']">
              {{ fmtChange(s.change_rate) }}
            </span>
          </div>

          <!-- Composite Badge -->
          <div class="composite-row">
            <el-tag :type="signalTagType(s.composite.signal)" size="small" effect="dark">
              {{ s.composite.label }}
            </el-tag>
            <span class="confidence">{{ (s.confidence * 100).toFixed(0) }}% 置信</span>
            <span class="profit-badge">{{ profitScore(s).toFixed(0) }}</span>
            <el-tag v-if="s.analysis.news_sentiment?.overall?.bullish" size="small" type="danger" effect="light" class="ns-card-badge">利好</el-tag>
            <el-tag v-else-if="s.analysis.news_sentiment?.overall?.signal === 'bearish'" size="small" type="success" effect="light" class="ns-card-badge">利空</el-tag>
          </div>

          <!-- Concepts & Limit-up -->
          <div class="tags-row">
            <el-tag v-if="s.limit_up?.is_limit_up" size="small" type="warning" effect="dark" class="limit-up-badge">
              {{ (s.limit_up.consecutive_limit_days ?? 0) > 1 ? `${s.limit_up.consecutive_limit_days}连板` : '涨停' }}
            </el-tag>
            <el-tag v-else-if="s.limit_up?.is_limit_down" size="small" type="success" effect="dark" class="limit-down-badge">跌停</el-tag>
            <el-tag v-for="c in (s.concepts || []).slice(0, 3)" :key="c" size="small" effect="plain" class="concept-chip">{{ c }}</el-tag>
            <el-tag v-if="s.trading_advice?.action_signal && s.trading_advice.action_signal !== 'hold'" size="small" :type="actionTagType(s.trading_advice.action_signal)" effect="dark" class="action-mini-badge">
              {{ actionLabel(s.trading_advice.action_signal) }}
            </el-tag>
          </div>

          <!-- Dual signal bars -->
          <div class="signal-bars">
            <div class="signal-bar-row">
              <span class="bar-label">短期</span>
              <el-progress
                :percentage="s.short_term.score"
                :color="scoreColor(s.short_term.score)"
                :stroke-width="10"
                :format="() => signalLabel(s.short_term.signal)"
              />
            </div>
            <div class="signal-bar-row">
              <span class="bar-label">长期</span>
              <el-progress
                :percentage="s.long_term.score"
                :color="scoreColor(s.long_term.score)"
                :stroke-width="10"
                :format="() => signalLabel(s.long_term.signal)"
              />
            </div>
          </div>

          <!-- Reasons preview -->
          <div class="reasons-preview">
            <div v-if="s.short_term.reasons?.length" class="reason-line short-reason">
              <el-icon size="12"><Top /></el-icon> {{ s.short_term.reasons[0] }}
            </div>
            <div v-if="s.long_term.reasons?.length" class="reason-line long-reason">
              <el-icon size="12"><Timer /></el-icon> {{ s.long_term.reasons[0] }}
            </div>
          </div>

          <!-- Price Prediction -->
          <div v-if="s.price_prediction?.target_price" class="pp-row">
            <el-tag :type="adviceTagType(s.trading_advice?.action_signal)" size="small" effect="dark" class="pp-action-tag">
              {{ s.trading_advice?.action || '--' }}
            </el-tag>
            <span class="pp-row-target">目标 <strong class="up">{{ fmtPrice(s.price_prediction.target_price) }}</strong></span>
            <span class="pp-row-stop">止损 <strong class="down">{{ fmtPrice(s.price_prediction.stop_loss) }}</strong></span>
            <span class="pp-row-return">预期 <strong :class="s.price_prediction.expected_return >= 0 ? 'up' : 'down'">{{ s.price_prediction.expected_return >= 0 ? '+' : '' }}{{ s.price_prediction.expected_return.toFixed(1) }}%</strong></span>
            <span :class="['pp-row-risk', riskLevelClass(s.price_prediction.risk_level)]">{{ s.price_prediction.risk_level }}</span>
          </div>

          <!-- Divergence -->
          <div v-if="s.composite.divergence" class="divergence-tip">
            {{ s.composite.divergence }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!loading && filteredSignals.length === 0" description="暂无监控信号" />
  </div>
</template>

<script setup lang="ts">
import { Top, Timer } from '@element-plus/icons-vue'
import type { MonitorSignal } from '@/api/monitor'

const props = defineProps<{
  filteredSignals: MonitorSignal[]
  loading: boolean
}>()

defineEmits<{
  (e: 'show-detail', s: MonitorSignal): void
}>()

function profitScore(s: MonitorSignal): number {
  const pp = s.price_prediction
  const adv = s.trading_advice
  if (!pp) return s.composite.score || 50
  const expRet = pp.expected_return || 0
  const rr = adv?.risk_reward_ratio || 0
  const comp = s.composite.score || 50
  return comp * 0.40 + Math.min(Math.max(expRet, 0) * 2, 100) * 0.35 + Math.min(rr * 10, 100) * 0.25
}

function fmtPrice(v: number | undefined | null): string {
  if (v == null || v === 0) return '--'
  return '¥' + v.toFixed(2)
}

function fmtChange(v: number | undefined | null): string {
  if (v == null) return '--'
  const sign = v >= 0 ? '+' : ''
  return sign + v.toFixed(2) + '%'
}

function signalLabel(sig: string): string {
  const map: Record<string, string> = { strong_buy: '强烈买入', buy: '买入', hold: '持有', sell: '卖出', strong_sell: '强烈卖出' }
  return map[sig] || sig
}

function signalTagType(sig: string): string {
  if (sig === 'strong_buy' || sig === 'buy') return 'danger'
  if (sig === 'sell' || sig === 'strong_sell') return 'success'
  return 'info'
}

function scoreColor(score: number): string {
  if (score >= 75) return '#f56c6c'
  if (score >= 60) return '#e6a23c'
  if (score >= 40) return '#909399'
  return '#67c23a'
}

function adviceTagType(signal?: string): string {
  if (signal === 'buy' || signal === 'add') return 'danger'
  if (signal === 'sell' || signal === 'reduce') return 'success'
  if (signal === 'watch') return 'info'
  return 'warning'
}

function actionTagType(signal?: string): string {
  if (signal === 'buy') return 'danger'
  if (signal === 'add') return 'warning'
  if (signal === 'reduce') return 'info'
  if (signal === 'sell') return 'success'
  return 'info'
}

function actionLabel(signal?: string): string {
  const map: Record<string, string> = { buy: '买入', add: '加仓', reduce: '减仓', sell: '卖出' }
  return map[signal || ''] || ''
}

function riskLevelClass(level: string): string {
  if (level === '低') return 'risk-low'
  if (level === '高') return 'risk-high'
  return 'risk-mid'
}
</script>

<style scoped>
.signal-grid {
  flex: 1;
  overflow-y: auto;
}

.signal-card {
  margin-bottom: 12px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.signal-card:hover {
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stock-code {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 13px;
  color: var(--text-muted, #999);
}

.stock-name {
  font-size: 15px;
  font-weight: 600;
}

.card-price {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}

.price-val {
  font-size: 20px;
  font-weight: 700;
  font-family: 'IBM Plex Mono', monospace;
}

.change { font-size: 13px; font-weight: 600; }
.change.up { color: #f56c6c; }
.change.down { color: #67c23a; }

.composite-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.confidence { font-size: 12px; color: var(--text-muted, #999); }
.profit-badge {
  font-size: 10px;
  font-weight: 700;
  font-family: 'IBM Plex Mono', monospace;
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--el-color-success-light-7, #e1f3d8);
  color: #67c23a;
}

.signal-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.signal-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-label {
  font-size: 11px;
  color: var(--text-muted, #999);
  width: 28px;
  flex-shrink: 0;
}

.reasons-preview {
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.reason-line {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.short-reason { color: #e6a23c; }
.long-reason { color: #409eff; }

.ns-card-badge {
  margin-left: auto;
  font-size: 10px;
  padding: 0 4px;
  height: 18px;
  line-height: 18px;
}

/* Tags Row */
.tags-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.limit-up-badge { font-size: 10px; padding: 0 4px; height: 18px; line-height: 18px; }
.limit-down-badge { font-size: 10px; padding: 0 4px; height: 18px; line-height: 18px; }
.concept-chip { font-size: 10px; padding: 0 4px; height: 18px; line-height: 18px; color: #F23645; border-color: #F23645; }
.action-mini-badge { font-size: 10px; font-weight: 700; padding: 0 4px; height: 18px; line-height: 18px; }

.divergence-tip {
  margin-top: 6px;
  padding: 4px 8px;
  background: var(--el-color-warning-light-9, #fdf6ec);
  border-radius: 4px;
  font-size: 11px;
  color: #e6a23c;
}

/* Price Prediction Row */
.pp-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  padding: 4px 6px;
  background: var(--el-color-info-light-9, #f4f4f5);
  border-radius: 4px;
  font-size: 11px;
  flex-wrap: wrap;
}
.pp-row-target, .pp-row-stop, .pp-row-return { white-space: nowrap; font-size: 10px; }
.pp-action-tag { font-size: 10px; padding: 0 4px; height: 18px; line-height: 18px; }
.pp-row-risk {
  margin-left: auto;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
}
.pp-row-risk.risk-low { background: #e1f3d8; color: #67c23a; }
.pp-row-risk.risk-mid { background: #faecd8; color: #e6a23c; }
.pp-row-risk.risk-high { background: #fde2e2; color: #f56c6c; }

</style>
