<template>
  <el-card class="fp-head-card" shadow="never">
    <div class="fp-head">
      <div class="fp-head-main">
        <div class="fp-mkt">
          <span class="fp-mkt-label">当前市场</span>
          <el-tag :type="stateTagType(marketState?.state)" effect="dark" round size="small">
            {{ stateText(marketState?.state) }}
          </el-tag>
          <div class="fp-mkt-weights">
            <div v-for="dim in DIMS" :key="dim.key" class="fp-wchip">
              <span class="fp-wname">{{ dim.label }}</span>
              <span class="fp-wbar"><i :style="{ width: weightPct(activeWeights?.[dim.key]) + '%', background: dim.color }"></i></span>
              <span class="fp-wpct">{{ ((activeWeights?.[dim.key] || 0) * 100).toFixed(0) }}</span>
            </div>
          </div>
          <el-tooltip v-if="marketState?.weights_optimized" placement="top"
                      :content="`权重已被回测优化 · ${fmtTime(marketState.last_optimized_at)}`">
            <el-tag size="small" type="success" effect="plain" round>权重已优化</el-tag>
          </el-tooltip>
        </div>

        <div class="fp-head-divider"></div>

        <div class="fp-params">
          <div class="fp-field-inline">
            <label>精选数量</label>
            <el-input-number v-model="localTopN" :min="3" :max="30" :step="1" size="small" controls-position="right" class="fp-num" />
          </div>
          <div class="fp-field-inline">
            <label>候选池</label>
            <el-input-number v-model="localCandidatePool" :min="20" :max="120" :step="10" size="small" controls-position="right" class="fp-num" />
          </div>
        </div>

        <el-collapse v-model="advancedOpen" class="fp-advanced">
          <el-collapse-item name="adv">
            <template #title>
              <span class="fp-adv-title">高级选项</span>
              <span class="fp-adv-hint">
                {{ advSummary }}
              </span>
            </template>

            <div class="fp-field fp-field-wide">
              <label>
                叠加策略
                <el-tooltip placement="top" content="把命中你认同风格策略的股票加「协同分」(每多1个来源+3，最多+9)。建议选 2-3 个，不是越多越好；不选=纯全市场量化。">
                  <el-icon class="fp-help"><QuestionFilled /></el-icon>
                </el-tooltip>
              </label>
              <div class="fp-combos">
                <span class="fp-combo-hint">推荐组合</span>
                <el-tag class="fp-combo" type="warning" effect="plain" round @click="applyCombo('market')">
                  🎯 跟随当前{{ stateText(marketState?.state) }}
                </el-tag>
                <el-tag class="fp-combo" effect="plain" round @click="applyCombo('value')">🛡️ 稳健价值</el-tag>
                <el-tag class="fp-combo" effect="plain" round @click="applyCombo('growth')">🚀 进攻成长</el-tag>
                <el-tag class="fp-combo" effect="plain" round @click="applyCombo('short')">⚡ 短线博弈</el-tag>
                <el-button v-if="localSelectedStrategyIds.length" link size="small" @click="localSelectedStrategyIds = []">清空</el-button>
              </div>
              <el-select v-model="localSelectedStrategyIds" multiple collapse-tags collapse-tags-tooltip
                         placeholder="不选 = 纯全市场量化初筛" size="small" filterable popper-class="fp-opt-popper">
                <el-option v-for="s in strategies" :key="s._id" :label="s.name" :value="s._id">
                  <span style="font-weight:500">{{ s.name }}</span>
                  <span style="margin-left:10px;font-size:12px;color:var(--el-text-color-secondary)">{{ s.description }}</span>
                </el-option>
              </el-select>
            </div>

            <div class="fp-field fp-field-wide">
              <label>
                投资哲学
                <el-tooltip placement="top" content="多种流派(价值/成长/趋势…)对同一只股各投票，越一致看多则加「辩论分」(±最多15)。不选=全部流派参与，分歧会互相抵消，结果更保守。">
                  <el-icon class="fp-help"><QuestionFilled /></el-icon>
                </el-tooltip>
              </label>
              <el-select v-model="localSelectedPhilosophyIds" multiple collapse-tags collapse-tags-tooltip
                         placeholder="不选 = 全部流派参与辩论" size="small" filterable popper-class="fp-opt-popper">
                <el-option v-for="a in philosophies" :key="a.id" :label="a.name" :value="a.id">
                  <span style="font-weight:500">{{ a.name }}</span>
                  <span style="margin-left:10px;font-size:12px;color:var(--el-text-color-secondary)">{{ a.description }}</span>
                </el-option>
              </el-select>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div class="fp-head-side">
        <div class="fp-side-title">融合选股引擎</div>
        <div class="fp-side-sub">市场感知 · 多策略叠加 · 多流派辩论</div>
        <el-button v-if="!running" type="primary" :icon="MagicStick" @click="$emit('run-pick')" :loading="loading" class="fp-cta">开始智选</el-button>
        <el-button v-else type="danger" plain @click="$emit('cancel-pick')" class="fp-cta-cancel">取消</el-button>
        <el-tag v-if="showDoneTip" type="success" effect="light" round size="small">智选完成 ✓</el-tag>
      </div>
    </div>

    <div v-if="running || progress.progress > 0" class="fp-progress">
      <el-progress
        :percentage="progress.progress"
        :status="progress.progress >= 100 ? 'success' : undefined"
        :stroke-width="14"
        striped striped-flow
      />
      <div class="fp-progress-status">{{ progress.status }}</div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { MagicStick, QuestionFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FusionMarketState, DimWeights, FusionPickProgress } from '@/api/fusionPick'

const props = defineProps<{
  marketState: FusionMarketState | null
  activeWeights: DimWeights | undefined
  topN: number
  candidatePool: number
  selectedStrategyIds: string[]
  selectedPhilosophyIds: string[]
  strategies: any[]
  philosophies: any[]
  running: boolean
  loading: boolean
  showDoneTip: boolean
  progress: FusionPickProgress
}>()

const emit = defineEmits<{
  (e: 'update:topN', val: number): void
  (e: 'update:candidatePool', val: number): void
  (e: 'update:selectedStrategyIds', val: string[]): void
  (e: 'update:selectedPhilosophyIds', val: string[]): void
  (e: 'run-pick'): void
  (e: 'cancel-pick'): void
}>()

const DIMS = [
  { key: 'fundamental', label: '基本面', color: '#5a7af0' },
  { key: 'technical', label: '技术面', color: 'var(--el-color-warning)' },
  { key: 'fund_flow', label: '资金面', color: 'var(--el-color-success)' },
  { key: 'valuation', label: '估值面', color: 'var(--text-muted)' },
] as const

const localTopN = computed({
  get: () => props.topN,
  set: (v) => emit('update:topN', v)
})
const localCandidatePool = computed({
  get: () => props.candidatePool,
  set: (v) => emit('update:candidatePool', v)
})
const localSelectedStrategyIds = computed({
  get: () => props.selectedStrategyIds,
  set: (v) => emit('update:selectedStrategyIds', v)
})
const localSelectedPhilosophyIds = computed({
  get: () => props.selectedPhilosophyIds,
  set: (v) => emit('update:selectedPhilosophyIds', v)
})

const advancedOpen = ref<string[]>([])

const COMBOS: Record<string, { label: string; names: string[] }> = {
  value:  { label: '稳健价值', names: ['QARP 质量价值', '红利低波防御', '五因子增强'] },
  growth: { label: '进攻成长', names: ['GARP 成长价值', '因子动量轮动', '行业轮动先锋'] },
  short:  { label: '短线博弈', names: ['交易型阿尔法', '行业轮动先锋'] },
}

function stateText(s?: string) { return s === 'bull' ? '牛市' : s === 'bear' ? '熊市' : '震荡市' }
function stateTagType(s?: string) { return s === 'bull' ? 'danger' : s === 'bear' ? 'success' : 'info' }
function weightPct(v?: number) { return Math.round((v || 0) * 100) }
function fmtTime(t?: string | null) {
  if (!t) return ''
  try { return new Date(t).toLocaleString('zh-CN', { hour12: false }) } catch { return t }
}

function comboByMarket(): string {
  const s = props.marketState?.state
  if (s === 'bull') return 'growth'
  if (s === 'bear') return 'value'
  return 'value'
}

function applyCombo(key: string) {
  const realKey = key === 'market' ? comboByMarket() : key
  const combo = COMBOS[realKey]
  if (!combo) return
  if (!props.strategies.length) { ElMessage.warning('策略列表尚未加载'); return }
  const ids = props.strategies.filter(s => combo.names.includes(s.name)).map(s => s._id)
  if (!ids.length) { ElMessage.warning('未匹配到对应策略'); return }
  localSelectedStrategyIds.value = ids
  if (!advancedOpen.value.includes('adv')) advancedOpen.value = ['adv']
  const byMarket = key === 'market' ? `（按当前${stateText(props.marketState?.state)}）` : ''
  ElMessage.success(`已应用「${combo.label}」组合${byMarket}：${combo.names.join('、')}`)
}

const advSummary = computed(() => {
  const s = localSelectedStrategyIds.value.length
  const p = localSelectedPhilosophyIds.value.length
  if (!s && !p) return '默认：全市场量化 + 全部流派辩论'
  const parts: string[] = []
  if (s) parts.push(`叠加 ${s} 策略`)
  parts.push(p ? `${p} 个指定流派` : '全部流派辩论')
  return parts.join(' · ')
})
</script>

<style scoped>
.fp-head-card :deep(.el-card__body) { padding: 16px 18px; }
.fp-mkt { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 14px; }
.fp-mkt-label { font-size: 13px; color: var(--text-secondary); }
.fp-mkt-weights { display: flex; align-items: center; flex-wrap: wrap; gap: 18px; margin-left: 4px; }
.fp-wchip { display: flex; align-items: center; gap: 6px; }
.fp-wname { font-size: 12px; color: var(--text-secondary); }
.fp-wbar { display: inline-block; width: 54px; height: 6px; border-radius: 3px; background: var(--el-fill-color, #eef0f3); overflow: hidden; }
.fp-wbar > i { display: block; height: 100%; border-radius: 3px; }
.fp-wpct { font-size: 12px; font-weight: 600; color: var(--text-primary); min-width: 20px; }
.fp-head-divider { height: 1px; background: var(--el-border-color-lighter); margin: 14px 0; }

.fp-head { display: flex; align-items: stretch; gap: 20px; }
.fp-head-main { flex: 1 1 auto; min-width: 0; }
.fp-head-side {
  flex: 0 0 240px; display: flex; flex-direction: column; justify-content: center; gap: 6px;
  padding: 18px; border-radius: 12px;
  background: linear-gradient(160deg, var(--el-fill-color-light), var(--el-fill-color));
}
.fp-side-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.fp-side-sub { font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin-bottom: 8px; }
.fp-params { display: flex; align-items: flex-end; flex-wrap: wrap; gap: 16px; }
.fp-field-inline { display: flex; flex-direction: column; gap: 6px; }
.fp-field-inline label { font-size: 12px; color: var(--text-secondary); }
.fp-num { width: 118px; }
.fp-cta, .fp-cta-cancel { width: 100%; }
@media (max-width: 860px) { .fp-head { flex-direction: column; } .fp-head-side { flex-basis: auto; } }
.fp-field { display: flex; flex-direction: column; gap: 6px; }
.fp-field-wide { grid-column: span 2; }
.fp-field label { font-size: 12px; color: var(--text-secondary); }
.fp-advanced { margin-top: 14px; border: none; border-top: 1px solid var(--el-border-color-lighter); }
.fp-advanced :deep(.el-collapse-item__header) { border: none; height: 44px; }
.fp-advanced :deep(.el-collapse-item__arrow) { margin-left: 6px; margin-right: auto; }
.fp-advanced :deep(.el-collapse-item__wrap) { border: none; }
.fp-advanced :deep(.el-collapse-item__content) { padding: 8px 2px 0; display: flex; flex-direction: column; gap: 12px; }
.fp-adv-title { font-size: 13px; color: var(--text-primary); font-weight: 500; margin-right: 10px; }
.fp-adv-hint { font-size: 12px; color: var(--text-secondary); }
.fp-help { font-size: 13px; color: var(--text-secondary); vertical-align: -2px; margin-left: 2px; cursor: help; }
.fp-combos { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 2px 0 2px; }
.fp-combo-hint { font-size: 12px; color: var(--text-secondary); margin-right: 2px; }
.fp-combo { cursor: pointer; transition: transform .1s; }
.fp-combo:hover { transform: translateY(-1px); }
.fp-progress { margin-top: 14px; }
.fp-progress-status { margin-top: 6px; font-size: 12px; color: var(--text-secondary); }

.fp-head-card {
  border-radius: 14px;
  border: 1px solid var(--el-border-color-lighter);
  box-shadow: 0 1px 3px rgba(0, 0, 0, .04);
}
.fp-wbar { width: 56px; height: 7px; border-radius: 4px; }
.fp-cta {
  height: 40px; padding: 0 22px; font-size: 14px; font-weight: 600;
  border: none; border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 6px 16px rgba(99, 102, 241, .28);
}
.fp-cta:hover { background: linear-gradient(135deg, #5457e6, #7c4ddc); }
</style>
