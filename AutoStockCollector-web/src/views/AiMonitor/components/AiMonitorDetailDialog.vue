<template>
  <el-dialog
    v-model="localVisible"
    :title="detailData?.name || detailData?.code"
    width="800px"
    top="5vh"
    class="detail-dialog"
    destroy-on-close
  >
    <template v-if="detailData">
      <div class="detail-header">
        <span class="dl-code">{{ detailData.code }}</span>
        <el-tag :type="detailData.type === '持仓' ? 'warning' : 'info'" size="small">
          {{ detailData.type }}
        </el-tag>
        <span v-if="detailData.industry" class="dl-industry">{{ detailData.industry }}</span>
      </div>
      <div class="detail-price">
        现价: <strong>{{ fmtPrice(detailData.price) }}</strong>
        <span :class="['change', detailData.change_rate >= 0 ? 'up' : 'down']">
          {{ fmtChange(detailData.change_rate) }}
        </span>
      </div>

      <!-- AI Trading Advice -->
      <el-card v-if="detailData.trading_advice" shadow="never" :class="['dl-advice', 'advice-' + (detailData.trading_advice.action_signal || 'hold')]">
        <div class="advice-header">
          <span class="advice-label">AI 操作建议</span>
          <el-tag :type="adviceTagType(detailData.trading_advice.action_signal)" size="large" effect="dark">
            {{ detailData.trading_advice.action }}
          </el-tag>
        </div>
        <div class="advice-body">
          <div class="advice-summary">{{ detailData.trading_advice.advice?.summary || detailData.trading_advice.reason }}</div>

          <div class="advice-price-row">
            <div class="adv-price-item" v-if="detailData.trading_advice.action_signal === 'buy'">
              <span class="ap-label">建议买入</span>
              <span class="ap-value up">{{ fmtPrice(detailData.trading_advice.advice?.buy_price_low) }} ~ {{ fmtPrice(detailData.trading_advice.advice?.buy_price_high) }}</span>
            </div>
            <div class="adv-price-item">
              <span class="ap-label">目标卖出</span>
              <span class="ap-value up">{{ fmtPrice(detailData.trading_advice.advice?.target_price) }} <small v-if="detailData.trading_advice.advice?.expected_return">(+{{ detailData.trading_advice.advice.expected_return.toFixed(1) }}%)</small></span>
            </div>
            <div class="adv-price-item">
              <span class="ap-label">止损价</span>
              <span class="ap-value down">{{ fmtPrice(detailData.trading_advice.advice?.stop_loss_price) }} <small v-if="detailData.trading_advice.advice?.max_loss">(-{{ detailData.trading_advice.advice.max_loss.toFixed(1) }}%)</small></span>
            </div>
            <div class="adv-price-item" v-if="detailData.trading_advice.advice?.hold_period">
              <span class="ap-label">持有策略</span>
              <span class="ap-value">{{ detailData.trading_advice.advice?.hold_period }}</span>
            </div>
          </div>

          <div class="advice-tags-row">
            <el-tag v-if="detailData.trading_advice.advice?.time_horizon" size="small" type="info" effect="plain">
              建议持有期: {{ detailData.trading_advice.advice.time_horizon }}
            </el-tag>
            <el-tag v-if="detailData.trading_advice.advice?.confidence_level" size="small" :type="confLevelType(detailData.trading_advice.advice.confidence_level)" effect="dark">
              置信度 {{ detailData.trading_advice.advice.confidence_level }}
            </el-tag>
            <el-tag v-if="detailData.trading_advice.reflection?.summary" size="small" type="warning" effect="plain" class="reflection-tag">
              {{ detailData.trading_advice.reflection.summary }}
            </el-tag>
          </div>

          <div v-if="detailData.trading_advice.divergence_warnings?.length" class="advice-divergence">
            <span class="div-icon">⚡</span>
            <span v-for="(w, i) in detailData.trading_advice.divergence_warnings" :key="i" class="div-item">{{ w }}</span>
          </div>
        </div>
        <div class="advice-metrics">
          <div class="adv-metric">
            <span class="adv-m-label">盈亏比</span>
            <span class="adv-m-val">{{ detailData.trading_advice.risk_reward_ratio }}</span>
          </div>
          <div class="adv-metric">
            <span class="adv-m-label">当前相对</span>
            <span class="adv-m-val">{{ detailData.trading_advice.current_position }}</span>
          </div>
          <div class="adv-metric">
            <span class="adv-m-label">距目标</span>
            <span class="adv-m-val">{{ detailData.trading_advice.distance_to_target }}</span>
          </div>
          <div class="adv-metric">
            <span class="adv-m-label">仓位建议</span>
            <span class="adv-m-val">{{ ((detailData.price_prediction?.position_size ?? 0) * 100).toFixed(0) }}%</span>
          </div>
        </div>
        <!-- 多维度评分条 -->
        <div v-if="detailData.trading_advice.details" class="advice-dims">
          <div v-for="(v, k) in detailData.trading_advice.details" :key="k" class="dim-row">
            <span class="dim-label">{{ dimLabel(k.toString()) }}</span>
            <div class="dim-bar-bg">
              <div class="dim-bar-fill" :style="{ width: v + '%', background: scoreColor(Number(v)) }"></div>
            </div>
            <span class="dim-score" :style="{ color: scoreColor(Number(v)) }">{{ v }}</span>
          </div>
        </div>
      </el-card>

      <!-- Signal Comparison -->
      <el-row :gutter="16" class="dl-signals">
        <el-col :span="12">
          <div class="dl-signal-box short-box">
            <div class="dl-signal-header">短期建议</div>
            <div class="dl-signal-value">
              <el-tag :type="signalTagType(detailData.short_term.signal)" size="large" effect="dark">
                {{ detailData.short_term.signal_label || detailData.short_term.signal }}
              </el-tag>
              <span class="dl-score">{{ detailData.short_term.score }}</span>
            </div>
            <el-progress
              :percentage="detailData.short_term.score"
              :color="scoreColor(detailData.short_term.score)"
              :stroke-width="8"
              :show-text="false"
            />
            <div class="dl-breakdown">
              <div v-for="(v, k) in detailData.short_term.breakdown" :key="k" class="bd-item">
                <span class="bd-label">{{ k }}</span>
                <span :style="{ color: scoreColor(Number(v)) }">{{ v }}</span>
              </div>
            </div>
            <ul class="dl-reasons">
              <li v-for="(r, i) in detailData.short_term.reasons" :key="i">{{ r }}</li>
            </ul>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="dl-signal-box long-box">
            <div class="dl-signal-header">长期建议</div>
            <div class="dl-signal-value">
              <el-tag :type="signalTagType(detailData.long_term.signal)" size="large" effect="dark">
                {{ detailData.long_term.signal_label || detailData.long_term.signal }}
              </el-tag>
              <span class="dl-score">{{ detailData.long_term.score }}</span>
            </div>
            <el-progress
              :percentage="detailData.long_term.score"
              :color="scoreColor(detailData.long_term.score)"
              :stroke-width="8"
              :show-text="false"
            />
            <div class="dl-breakdown">
              <div v-for="(v, k) in detailData.long_term.breakdown" :key="k" class="bd-item">
                <span class="bd-label">{{ k }}</span>
                <span :style="{ color: scoreColor(Number(v)) }">{{ v }}</span>
              </div>
            </div>
            <ul class="dl-reasons">
              <li v-for="(r, i) in detailData.long_term.reasons" :key="i">{{ r }}</li>
            </ul>
          </div>
        </el-col>
      </el-row>

      <!-- Composite + Price Prediction -->
      <el-row :gutter="16" class="dl-summary">
        <el-col :span="14">
          <el-card shadow="never" class="dl-composite">
            <div class="dl-comp-row">
              <span class="comp-label">综合评分</span>
              <span class="comp-score" :style="{ color: scoreColor(detailData.composite.score) }">
                {{ detailData.composite.score }}
              </span>
              <el-tag :type="signalTagType(detailData.composite.signal)" effect="dark">
                {{ detailData.composite.label }}
              </el-tag>
              <span class="comp-conf">置信度: {{ (detailData.confidence * 100).toFixed(0) }}%</span>
              <span v-if="detailData.composite.divergence" class="comp-div">
                {{ detailData.composite.divergence }}
              </span>
            </div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card shadow="never" class="dl-composite" v-if="detailData.price_prediction">
            <div class="pp-summary">
              <div class="pp-sum-item">
                <span class="pp-sum-label">买入区间</span>
                <span class="pp-sum-val up">{{ fmtPrice(detailData.price_prediction.buy_zone_low) }} ~ {{ fmtPrice(detailData.price_prediction.buy_zone_high) }}</span>
              </div>
              <div class="pp-sum-item">
                <span class="pp-sum-label">支撑/阻力</span>
                <span class="pp-sum-val">{{ fmtPrice(detailData.price_prediction.support) }} / {{ fmtPrice(detailData.price_prediction.resistance) }}</span>
              </div>
              <div class="pp-sum-item">
                <span class="pp-sum-label">波动率</span>
                <span class="pp-sum-val">{{ detailData.price_prediction.volatility?.toFixed(1) }}%</span>
              </div>
              <div class="pp-sum-item">
                <span class="pp-sum-label">风险</span>
                <span :class="['pp-sum-val pp-risk-tag', riskLevelClass(detailData.price_prediction.risk_level)]">
                  {{ detailData.price_prediction.risk_level }}
                </span>
              </div>
              <div class="pp-sum-item">
                <span class="pp-sum-label">仓位建议</span>
                <span class="pp-sum-val">{{ (detailData.price_prediction.position_size * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Analysis Breakdown -->
      <el-tabs class="dl-tabs" v-model="localDetailTab">
        <el-tab-pane label="资金流向" name="fund_flow">
          <div class="tab-content">
            <div class="tab-sub">
              <h4>短期资金</h4>
              <p>评分: {{ detailData.analysis.fund_flow.short_term.score }} / 信号: {{ detailData.analysis.fund_flow.short_term.signal }}</p>
              <ul><li v-for="r in detailData.analysis.fund_flow.short_term.reasons" :key="r">{{ r }}</li></ul>
            </div>
            <div class="tab-sub">
              <h4>长期资金</h4>
              <p>评分: {{ detailData.analysis.fund_flow.long_term.score }} / 信号: {{ detailData.analysis.fund_flow.long_term.signal }}</p>
              <ul><li v-for="r in detailData.analysis.fund_flow.long_term.reasons" :key="r">{{ r }}</li></ul>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="研报分析" name="research">
          <div class="tab-content">
            <p>研报数量: {{ detailData.analysis.research.report_count || 0 }}</p>
            <div class="tab-sub">
              <h4>短期研报</h4>
              <p>评分: {{ detailData.analysis.research.short_term.score }} / 近{{ detailData.analysis.research.short_term.recent_count || 0 }}份</p>
              <ul><li v-for="r in detailData.analysis.research.short_term.reasons" :key="r">{{ r }}</li></ul>
            </div>
            <div class="tab-sub">
              <h4>长期研报</h4>
              <p>评分: {{ detailData.analysis.research.long_term.score }} / 共{{ detailData.analysis.research.long_term.total_reports || 0 }}份</p>
              <ul><li v-for="r in detailData.analysis.research.long_term.reasons" :key="r">{{ r }}</li></ul>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="技术面" name="technical">
          <div class="tab-content">
            <div class="tab-sub">
              <h4>短期技术</h4>
              <p>评分: {{ detailData.analysis.technical.short_term.score }} / 信号: {{ detailData.analysis.technical.short_term.signal }}</p>
              <ul><li v-for="r in detailData.analysis.technical.short_term.reasons" :key="r">{{ r }}</li></ul>
            </div>
            <div class="tab-sub">
              <h4>长期技术</h4>
              <p>评分: {{ detailData.analysis.technical.long_term.score }} / 信号: {{ detailData.analysis.technical.long_term.signal }}</p>
              <ul><li v-for="r in detailData.analysis.technical.long_term.reasons" :key="r">{{ r }}</li></ul>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="基本面" name="fundamental">
          <div class="tab-content">
            <p>评分: {{ detailData.analysis.fundamental.score }} / 信号: {{ detailData.analysis.fundamental.signal }}</p>
            <ul><li v-for="r in detailData.analysis.fundamental.reasons" :key="r">{{ r }}</li></ul>
            <div v-if="detailData.analysis.fundamental.details" class="detail-grid">
              <div v-for="(v, k) in detailData.analysis.fundamental.details" :key="k" class="detail-item">
                <span class="di-label">{{ k }}</span>
                <span class="di-value">{{ v ?? '--' }}</span>
              </div>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="估值面" name="valuation">
          <div class="tab-content" v-if="detailData.analysis.valuation">
            <p>评分: {{ detailData.analysis.valuation.score }} / 信号: {{ detailData.analysis.valuation.signal }}</p>
            <ul><li v-for="r in detailData.analysis.valuation.reasons" :key="r">{{ r }}</li></ul>
            <div v-if="detailData.analysis.valuation.details" class="detail-grid">
              <div v-for="(v, k) in detailData.analysis.valuation.details" :key="k" class="detail-item">
                <span class="di-label">{{ k }}</span>
                <span class="di-value">{{ v ?? '--' }}</span>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
      <!-- Price Prediction Detail (可折叠) -->
      <el-collapse v-if="detailData.price_prediction" class="pp-collapse">
        <el-collapse-item title="价格预测详情 (点击展开)" name="pp-detail">
          <div class="pp-detail-grid">
            <div class="pp-detail-item">
              <span class="pp-dl-label">买入区间</span>
              <span class="pp-dl-val">{{ fmtPrice(detailData.price_prediction.buy_zone_low) }} ~ {{ fmtPrice(detailData.price_prediction.buy_zone_high) }}</span>
            </div>
            <div class="pp-detail-item">
              <span class="pp-dl-label">支撑位</span>
              <span class="pp-dl-val">{{ fmtPrice(detailData.price_prediction.support) }}</span>
            </div>
            <div class="pp-detail-item">
              <span class="pp-dl-label">阻力位</span>
              <span class="pp-dl-val">{{ fmtPrice(detailData.price_prediction.resistance) }}</span>
            </div>
            <div class="pp-detail-item">
              <span class="pp-dl-label">年化波动率</span>
              <span class="pp-dl-val">{{ detailData.price_prediction.volatility.toFixed(1) }}%</span>
            </div>
            <div class="pp-detail-item">
              <span class="pp-dl-label">最大亏损</span>
              <span class="pp-dl-val down">{{ detailData.price_prediction.max_loss.toFixed(1) }}%</span>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MonitorSignal } from '@/api/monitor'

const props = defineProps<{
  visible: boolean
  detailData: MonitorSignal | null
  detailTab: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'update:detailTab', val: string): void
}>()

const localVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const localDetailTab = computed({
  get: () => props.detailTab,
  set: (val) => emit('update:detailTab', val)
})

function fmtPrice(v: number | undefined | null): string {
  if (v == null || v === 0) return '--'
  return '¥' + v.toFixed(2)
}

function fmtChange(v: number | undefined | null): string {
  if (v == null) return '--'
  const sign = v >= 0 ? '+' : ''
  return sign + v.toFixed(2) + '%'
}

function adviceTagType(signal?: string): string {
  if (signal === 'buy') return 'danger'
  if (signal === 'sell') return 'success'
  if (signal === 'watch') return 'info'
  return 'warning'
}

function confLevelType(level: string): string {
  if (level === '高') return 'danger'
  if (level === '中') return 'warning'
  return 'info'
}

function riskLevelClass(level: string): string {
  if (level === '低') return 'risk-low'
  if (level === '高') return 'risk-high'
  return 'risk-mid'
}

function dimLabel(k: string): string {
  const m: Record<string, string> = { fund_flow_score: '主力资金', research_score: '研报', technical_score: '技术面', valuation_score: '估值', composite_score: '综合评分' }
  return m[k] || k
}

function scoreColor(score: number): string {
  if (score >= 75) return '#f56c6c'
  if (score >= 60) return '#e6a23c'
  if (score >= 40) return '#909399'
  return '#67c23a'
}

function signalTagType(sig: string): string {
  if (sig === 'strong_buy' || sig === 'buy') return 'danger'
  if (sig === 'sell' || sig === 'strong_sell') return 'success'
  return 'info'
}
</script>

<style scoped>
.change { font-size: 13px; font-weight: 600; }
.change.up { color: #f56c6c; }
.change.down { color: #67c23a; }

/* Detail Dialog */
.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dl-code {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 14px;
  color: var(--text-muted, #999);
}

.dl-industry {
  font-size: 12px;
  color: var(--text-muted, #999);
}

.detail-price {
  margin-bottom: 16px;
  font-size: 14px;
}

/* AI Trading Advice */
.dl-advice {
  margin-bottom: 16px;
  border-left: 4px solid #909399;
}
.dl-advice.advice-buy { border-left-color: #f56c6c; }
.dl-advice.advice-sell { border-left-color: #67c23a; }
.dl-advice.advice-watch { border-left-color: #909399; }
.dl-advice.advice-hold { border-left-color: #e6a23c; }
.advice-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.advice-label { font-size: 14px; font-weight: 700; }
.advice-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.advice-summary {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 10px;
  line-height: 1.5;
}
.advice-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 4px 0;
}
.reflection-tag {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.advice-divergence {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  padding: 6px 12px;
  margin-top: 6px;
  background: #fff7e6;
  border-radius: 4px;
  font-size: 12px;
  color: #d48806;
}
.advice-divergence .div-icon { font-size: 14px; }
.advice-divergence .div-item { line-height: 1.4; }
.advice-price-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 4px;
}
.adv-price-item {
  flex: 1;
  min-width: 120px;
  background: #fafafa;
  border-radius: 4px;
  padding: 6px 10px;
  text-align: center;
}
.adv-price-item .ap-label {
  display: block;
  font-size: 11px;
  color: #909399;
  margin-bottom: 2px;
}
.adv-price-item .ap-value {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}
.adv-price-item .ap-value small {
  font-size: 11px;
  font-weight: 400;
}
.adv-price-item .ap-value.up { color: #f56c6c; }
.adv-price-item .ap-value.down { color: #67c23a; }
.advice-metrics {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.adv-metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}
.adv-m-label { font-size: 10px; color: #999; }
.adv-m-val { font-size: 13px; font-weight: 600; }
.advice-dims {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.dim-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.dim-label { font-size: 11px; color: #999; width: 56px; flex-shrink: 0; }
.dim-bar-bg {
  flex: 1;
  height: 6px;
  background: var(--el-fill-color, #f0f0f0);
  border-radius: 3px;
  overflow: hidden;
}
.dim-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.dim-score { font-size: 11px; font-weight: 600; width: 24px; text-align: right; }

.dl-signals { margin-bottom: 16px; }

.dl-signal-box {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #eee);
}

.short-box { border-left: 3px solid #e6a23c; }
.long-box { border-left: 3px solid #409eff; }

.dl-signal-header {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-muted, #999);
}

.dl-signal-value {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.dl-score {
  font-size: 24px;
  font-weight: 700;
}

.dl-breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0;
}

.bd-item {
  font-size: 11px;
  padding: 2px 6px;
  background: var(--el-fill-color, #f5f5f5);
  border-radius: 4px;
}

.bd-label { margin-right: 4px; color: var(--text-muted, #999); }

.dl-reasons {
  margin: 8px 0 0;
  padding-left: 16px;
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.dl-reasons li { margin-bottom: 2px; }

.dl-composite { margin-bottom: 16px; }

.dl-comp-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.comp-label { font-size: 12px; color: var(--text-muted, #999); }
.comp-score { font-size: 28px; font-weight: 700; }
.comp-conf { font-size: 12px; color: var(--text-muted, #999); }
.comp-div { font-size: 11px; color: #e6a23c; }

.pp-summary {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.pp-sum-item { display: flex; flex-direction: column; align-items: center; min-width: 50px; }
.pp-sum-label { font-size: 10px; color: #999; }
.pp-sum-val { font-size: 14px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
.pp-sum-val.up { color: #f56c6c; }
.pp-sum-val.down { color: #67c23a; }
.pp-risk-tag { font-size: 11px; padding: 1px 4px; border-radius: 3px; }
.pp-risk-tag.risk-low { background: #e1f3d8; color: #67c23a; }
.pp-risk-tag.risk-mid { background: #faecd8; color: #e6a23c; }
.pp-risk-tag.risk-high { background: #fde2e2; color: #f56c6c; }

.dl-tabs { margin-top: 8px; }

.tab-content { padding: 8px 0; }
.tab-sub { margin-bottom: 12px; }
.tab-sub h4 { margin: 0 0 4px; font-size: 13px; }
.tab-sub p { font-size: 12px; color: var(--text-muted, #999); margin: 0 0 4px; }
.tab-sub ul { margin: 0; padding-left: 16px; font-size: 12px; }
.tab-sub li { margin-bottom: 2px; }

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.detail-item {
  padding: 6px 8px;
  background: var(--el-fill-color, #f5f5f5);
  border-radius: 4px;
}

.di-label {
  display: block;
  font-size: 11px;
  color: var(--text-muted, #999);
}

.di-value {
  display: block;
  font-size: 14px;
  font-weight: 600;
  font-family: 'IBM Plex Mono', monospace;
}

.dl-summary { margin-bottom: 16px; }
.pp-collapse { margin-bottom: 16px; }
.pp-detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.pp-detail-item {
  display: flex;
  flex-direction: column;
  padding: 6px 8px;
  background: var(--el-fill-color, #f5f5f5);
  border-radius: 4px;
}
.pp-dl-label { font-size: 11px; color: #999; }
.pp-dl-val { font-size: 14px; font-weight: 600; font-family: 'IBM Plex Mono', monospace; }
.pp-dl-val.down { color: #67c23a; }
</style>
