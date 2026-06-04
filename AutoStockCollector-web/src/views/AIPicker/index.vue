<template>
  <div class="ap-page">
    <div class="ap-toolbar">
      <div class="ap-title-group">
        <span class="ap-title">量化选股</span>
        <span class="ap-subtitle">多因子模型 · AI解读</span>
      </div>
      <div class="ap-controls">
        <el-input v-model.number="topN" size="small" style="width:110px"><template #prepend>选 N</template></el-input>
        <el-input v-model.number="candidatePool" size="small" style="width:140px"><template #prepend>候选池</template></el-input>
        <el-button type="primary" size="small" :loading="running" :disabled="running" @click="runPick">
          {{ running ? '运行中...' : '立即重跑' }}
        </el-button>
        <el-button size="small" :loading="loading" @click="loadResults">刷新结果</el-button>
      </div>
    </div>

    <!-- 进度条 -->
    <div v-if="progressData.is_running || showDoneTip" class="ap-progress-box">
      <template v-if="progressData.is_running">
        <div class="ap-progress-header">🔄 量化选股执行中</div>
        <el-progress :percentage="progressData.progress" :stroke-width="14" :color="'#5a7af0'" />
        <div class="ap-progress-status">{{ progressData.status }}</div>
      </template>
      <template v-else-if="showDoneTip">
        <div class="ap-progress-done">✅ 选股完成，结果已更新</div>
      </template>
    </div>

    <div v-if="result" class="ap-meta">
      <span>策略：{{ result.strategy }}</span>
      <span v-if="result.universe_count">全市场 {{ result.universe_count }} → 候选 {{ result.candidate_count }} → 精选 {{ result.picks.length }}</span>
      <span>更新：{{ fmtTime(result.timestamp) }}</span>
    </div>

    <el-table v-if="result?.picks?.length" :data="result.picks" stripe class="ap-table"
              :row-class-name="tableRowClass" @row-click="toggleExpand">
      <el-table-column type="index" label="#" width="42" align="center" />
      <el-table-column prop="code" label="代码" width="100">
        <template #default="{ row }"><span class="ap-code" @click.stop="goAnalysis(row.code)">{{ row.code }}</span></template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="90" />
      <el-table-column label="综合" width="140" sortable :sort-by="(r: AIPick) => r.composite">
        <template #default="{ row }">
          <el-progress :percentage="Math.round(row.composite)" :color="scoreColor(row.composite)" :stroke-width="8" />
        </template>
      </el-table-column>
      <el-table-column label="基本" width="55" align="center" sortable :sort-by="(r: AIPick) => r.scores?.fundamental ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.fundamental != null" class="ap-score-cell" :style="{ color: dimColor(row.scores.fundamental) }">{{ Math.round(row.scores.fundamental) }}</span>
          <span v-else class="ap-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="技术" width="55" align="center" sortable :sort-by="(r: AIPick) => r.scores?.technical ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.technical != null" class="ap-score-cell" :style="{ color: dimColor(row.scores.technical) }">{{ Math.round(row.scores.technical) }}</span>
          <span v-else class="ap-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="资金" width="55" align="center" sortable :sort-by="(r: AIPick) => r.scores?.fund_flow ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.fund_flow != null" class="ap-score-cell" :style="{ color: dimColor(row.scores.fund_flow) }">{{ Math.round(row.scores.fund_flow) }}</span>
          <span v-else class="ap-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="估值" width="55" align="center" sortable :sort-by="(r: AIPick) => r.scores?.valuation ?? 0">
        <template #default="{ row }">
          <span v-if="row.scores?.valuation != null" class="ap-score-cell" :style="{ color: dimColor(row.scores.valuation) }">{{ Math.round(row.scores.valuation) }}</span>
          <span v-else class="ap-na">-</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="56" align="center">
        <template #default="{ row }">
          <span v-if="row.source === 'llm'" class="ap-source-tag ap-tag-ai">AI</span>
          <span v-else class="ap-source-tag ap-tag-factor">因子</span>
        </template>
      </el-table-column>
      <el-table-column width="36" align="center" class-name="ap-col-expand">
        <template #default="{ row }">
          <svg class="ap-expand-svg" :class="{ 'is-expanded': expandedCode === row.code }" viewBox="0 0 12 12" width="12" height="12">
            <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </template>
      </el-table-column>
    </el-table>

    <!-- 展开详情面板 -->
    <div v-if="expandedPick" class="ap-detail-panel">
      <div class="ap-detail-header">
        <span>{{ expandedPick.code }} {{ expandedPick.name }} 评分详情</span>
        <el-button size="small" text @click="expandedCode = ''">收起 ▲</el-button>
      </div>

      <div v-if="expandedPick.score_details && Object.keys(expandedPick.score_details).length" class="ap-detail-body">
        <div v-for="dim in orderedDimensions" :key="dim.key" class="ap-dim-block">
          <div class="ap-dim-title">
            <span class="ap-dim-label">{{ dim.label }}</span>
            <el-progress class="ap-dim-bar" :percentage="Math.round(dim.score)" :color="scoreColor(dim.score)" :stroke-width="8" />
            <span class="ap-dim-score">{{ dim.score }}分</span>
            <span class="ap-dim-weight">权重{{ Math.round(dim.weight * 100) }}%</span>
            <span class="ap-dim-contrib">贡献{{ dim.contribution }}分</span>
          </div>
          <div class="ap-dim-grid">
            <div v-for="si in dim.scoreItems" :key="si.key" class="ap-grid-cell">
              <div class="ap-cell-top">
                <span class="ap-cell-name">{{ formatItemName(si.key) }}</span>
                <span class="ap-cell-ratio" :style="{ color: ratioColor(si.item.score, si.item.max) }">{{ si.item.score }}/{{ si.item.max }}</span>
              </div>
              <div class="ap-cell-bottom">
                <span class="ap-cell-value">{{ formatItemValueRich(si.key, si.item) }}</span>
                <div class="ap-mini-bar">
                  <div class="ap-mini-fill" :style="{ width: (si.item.score / si.item.max * 100) + '%', background: ratioColor(si.item.score, si.item.max) }"></div>
                </div>
              </div>
            </div>
          </div>
          <div v-for="w in dimWarnings(dim)" :key="w" class="ap-dim-warning">⚠️ {{ w }}</div>
        </div>
      </div>
      <div v-else class="ap-detail-empty">
        详情数据不可用，请重新运行选股以生成详情
      </div>

      <div v-if="expandedPick.recommendation" class="ap-detail-advice">
        <div class="ap-advice-label">AI分析建议：</div>
        <div class="ap-advice-text md-content" v-html="renderMd(expandedPick.recommendation)"></div>
      </div>
    </div>

    <!-- AI 综合投资建议（折叠式） -->
    <div v-if="result?.ai_summary" class="ap-ai-summary">
      <div class="ap-summary-toggle" @click="summaryExpanded = !summaryExpanded">
        <span>🤖 AI 综合投资建议</span>
        <svg class="ap-summary-svg" :class="{ 'is-expanded': summaryExpanded }" viewBox="0 0 12 12" width="12" height="12">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div v-if="summaryExpanded" class="ap-summary-body md-content" v-html="renderMd(result.ai_summary)"></div>
    </div>

    <el-empty v-if="!result?.picks?.length && !loading" description="暂无选股结果，点击「立即重跑」" />

    <p v-if="result" class="ap-method-note">评分为运行时快照：K线取近30个交易日，财务取最新报告期，资金面取近5日均值，PE/PB由财报EPS推算</p>
    <p v-if="result" class="ap-disclaimer">{{ result.disclaimer }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import dayjs from 'dayjs'
import { aiServiceApi, type AIPickResult, type AIPick } from '@/api/ai'

marked.setOptions({ breaks: true, gfm: true })

function renderMd(text: string): string {
  if (!text) return ''
  return marked.parse(text) as string
}

const router = useRouter()
const result = ref<AIPickResult | null>(null)
const loading = ref(false)
const running = ref(false)
const topN = ref(10)
const candidatePool = ref(50)
const expandedCode = ref('')
const showDoneTip = ref(false)
const summaryExpanded = ref(false)

const progressData = ref<{ is_running: boolean; progress: number; status: string }>({
  is_running: false, progress: 0, status: '',
})
let progressTimer: ReturnType<typeof setInterval> | null = null

const expandedPick = computed(() => {
  if (!expandedCode.value || !result.value?.picks) return null
  return result.value.picks.find(p => p.code === expandedCode.value) || null
})

const DIM_LABELS: Record<string, string> = {
  fundamental: '基本面',
  technical: '技术面',
  fund_flow: '资金面',
  valuation: '估值面',
}
const DIM_ORDER = ['fundamental', 'technical', 'fund_flow', 'valuation']

const orderedDimensions = computed(() => {
  const pick = expandedPick.value
  if (!pick?.score_details) return []
  return DIM_ORDER.filter(k => k in pick.score_details).map(k => {
    const d = pick.score_details[k]
    const items = d.details ?? {}
    const scoreItems = Object.entries(items)
      .filter(([, v]) => typeof v === 'object' && v !== null && 'score' in (v as any))
      .map(([key, v]) => ({ key, item: v as any }))
    return {
      key: k,
      label: DIM_LABELS[k] || k,
      score: d.score ?? 0,
      weight: d.normalized_weight ?? d.weight ?? 0,
      contribution: d.contribution ?? 0,
      items,
      scoreItems,
    }
  })
})

const ITEM_NAMES: Record<string, string> = {
  roe: 'ROE',
  revenue_growth: '营收增速',
  profit_growth: '利润增速',
  gross_margin: '毛利率',
  debt_ratio: '资产负债率',
  ma_trend: '均线趋势',
  macd: 'MACD',
  rsi: 'RSI',
  momentum: '价格动量',
  net_inflow: '主力净流入',
  main_ratio: '主力占比',
  turnover_rate: '换手率',
  pe: 'PE',
  pb: 'PB',
}

const PCT_KEYS = new Set(['roe', 'revenue_growth', 'profit_growth', 'gross_margin', 'debt_ratio', 'turnover_rate', 'main_ratio', 'momentum'])

function dimWarnings(dim: any): string[] {
  if (!dim.items) return []
  return Object.entries(dim.items)
    .filter(([k, v]) => k.endsWith('_warning') && typeof v === 'string')
    .map(([, v]) => v as string)
}

function formatItemName(key: string): string {
  return ITEM_NAMES[key] || key
}

function formatItemValueRich(key: string, item: any): string {
  if (item.value == null && item.value_yi == null) return '无数据'
  if (typeof item.value === 'string') return item.value
  if (item.value_yi != null) return `${item.value_yi}亿`
  if (PCT_KEYS.has(key)) return `${item.value}%`
  if (key === 'pe' || key === 'pb') return Number(item.value).toFixed(2)
  return String(item.value)
}

function scoreColor(v: number): string {
  if (v >= 70) return '#3a8a52'
  if (v >= 50) return '#d0a020'
  return '#a04040'
}

function dimColor(v: number): string {
  if (v >= 80) return '#52c41a'
  if (v >= 60) return '#faad14'
  return '#ff4d4f'
}

function ratioColor(score: number, max: number): string {
  if (!max) return '#606070'
  const pct = score / max
  if (pct >= 0.8) return '#52c41a'
  if (pct >= 0.6) return '#faad14'
  return '#ff4d4f'
}

function tableRowClass({ row }: { row: AIPick }) {
  const classes = ['ap-row-clickable']
  if (row.code === expandedCode.value) classes.push('ap-row-active')
  return classes.join(' ')
}

function fmtTime(t: string): string {
  return t ? dayjs(t).format('MM-DD HH:mm') : '--'
}

function goAnalysis(code: string) {
  router.push({ path: '/stock-analysis', query: { code } })
}

function toggleExpand(row: AIPick) {
  expandedCode.value = expandedCode.value === row.code ? '' : row.code
}

async function loadResults() {
  loading.value = true
  try {
    const res = await aiServiceApi.pickResults()
    result.value = res.data?.data || null
  } catch {
    ElMessage.error('加载选股结果失败')
  } finally {
    loading.value = false
  }
}

function startProgressPolling() {
  stopProgressPolling()
  progressTimer = setInterval(async () => {
    try {
      const res = await aiServiceApi.pickProgress()
      const data = res.data?.data
      if (data) {
        progressData.value = data
        if (!data.is_running && data.progress >= 100) {
          stopProgressPolling()
          running.value = false
          showDoneTip.value = true
          await loadResults()
          setTimeout(() => { showDoneTip.value = false }, 4000)
        }
      }
    } catch { /* ignore */ }
  }, 3000)
}

function stopProgressPolling() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

async function runPick() {
  running.value = true
  showDoneTip.value = false
  progressData.value = { is_running: true, progress: 0, status: '正在启动...' }
  try {
    const res = await aiServiceApi.pickRun({ top_n: topN.value, candidate_pool: candidatePool.value })
    if (res.data?.success) {
      ElMessage.info('选股任务已启动')
      startProgressPolling()
    } else {
      ElMessage.error(res.data?.error || '选股失败')
      running.value = false
      progressData.value = { is_running: false, progress: 0, status: '' }
    }
  } catch {
    ElMessage.error('选股请求失败')
    running.value = false
    progressData.value = { is_running: false, progress: 0, status: '' }
  }
}

onMounted(async () => {
  await loadResults()
  try {
    const res = await aiServiceApi.pickProgress()
    const data = res.data?.data
    if (data?.is_running) {
      progressData.value = data
      running.value = true
      startProgressPolling()
    }
  } catch { /* ignore */ }
})

onBeforeUnmount(stopProgressPolling)
</script>

<style scoped>
.ap-page { display: flex; flex-direction: column; gap: 10px; }
.ap-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.ap-title-group { display: flex; align-items: baseline; gap: 10px; }
.ap-title { font-size: 15px; font-weight: 700; color: #d8daf0; }
.ap-subtitle { font-size: 12px; color: #606080; }
.ap-controls { display: flex; gap: 8px; align-items: center; }
.ap-meta { display: flex; gap: 18px; font-size: 12px; color: #606080; }

/* 表格 */
.ap-table { background: transparent; }
.ap-table :deep(.el-table__row) { height: 42px; }
.ap-table :deep(.el-table__row:hover > td) { background: rgba(255,255,255,0.04) !important; }
.ap-row-clickable { cursor: pointer; }
.ap-row-active :deep(td) {
  background: rgba(90,122,240,0.08) !important;
  border-left: 2px solid #5a7af0;
}
.ap-code { color: #5a7af0; cursor: pointer; }
.ap-code:hover { text-decoration: underline; }
.ap-na { color: #505060; }
.ap-score-cell { font-weight: 600; font-size: 13px; }
.ap-source-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.4;
}
.ap-tag-ai { color: #60a0f0; background: rgba(96,160,240,0.12); }
.ap-tag-factor { color: #a0a060; background: rgba(160,160,96,0.12); }
.ap-expand-svg {
  color: #606080;
  transition: transform 0.2s;
  vertical-align: middle;
}
.ap-expand-svg.is-expanded { transform: rotate(180deg); }
.ap-col-expand { overflow: visible !important; }
.ap-method-note { font-size: 11px; color: #44445a; text-align: center; margin-top: 8px; }
.ap-disclaimer { font-size: 11px; color: #44445a; text-align: center; }

/* 进度条 */
.ap-progress-box {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  padding: 12px 16px;
}
.ap-progress-header { font-size: 13px; color: #b0b0d0; margin-bottom: 8px; }
.ap-progress-status { font-size: 12px; color: #808098; margin-top: 6px; }
.ap-progress-done { font-size: 13px; color: #4ade80; text-align: center; padding: 4px 0; }

/* 展开详情面板 */
.ap-detail-panel {
  background: #1a1a2e;
  border: 1px solid #2a2a4a;
  border-radius: 8px;
  padding: 14px;
  margin-top: -4px;
}
.ap-detail-header {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 14px; font-weight: 600; color: #c0c0e0; margin-bottom: 10px;
}
.ap-detail-body { display: flex; flex-direction: column; gap: 10px; }
.ap-dim-block { background: #16162a; border-radius: 6px; padding: 10px 12px; }
.ap-dim-title {
  display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
}
.ap-dim-label { font-size: 13px; font-weight: 600; color: #b0b0d0; min-width: 48px; }
.ap-dim-bar { flex: 1; max-width: 180px; }
.ap-dim-score { font-size: 13px; font-weight: 600; color: #d8d8f0; }
.ap-dim-weight { font-size: 11px; color: #707090; }
.ap-dim-contrib { font-size: 11px; color: #808090; }

/* 子指标网格 */
.ap-dim-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}
@media (min-width: 900px) {
  .ap-dim-grid { grid-template-columns: repeat(3, 1fr); }
}
.ap-grid-cell {
  background: #1a1a32;
  border-radius: 4px;
  padding: 7px 10px;
}
.ap-cell-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 3px;
}
.ap-cell-name { font-size: 11px; color: #707088; }
.ap-cell-ratio { font-size: 11px; font-weight: 600; }
.ap-cell-bottom {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ap-cell-value { font-size: 14px; font-weight: 600; color: #d0d0e8; white-space: nowrap; }
.ap-mini-bar {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: rgba(255,255,255,0.08);
  min-width: 30px;
  max-width: 100px;
}
.ap-mini-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

.ap-dim-warning {
  margin-top: 6px;
  padding: 5px 10px;
  background: rgba(250, 173, 20, 0.12);
  border-left: 3px solid #faad14;
  border-radius: 4px;
  font-size: 12px;
  color: #faad14;
  line-height: 1.4;
}
.ap-detail-empty { color: #606070; font-size: 13px; text-align: center; padding: 16px 0; }
.ap-detail-advice { margin-top: 10px; border-top: 1px solid #2a2a4a; padding-top: 10px; }
.ap-advice-label { font-size: 12px; color: #808090; margin-bottom: 4px; }
.ap-advice-text { font-size: 13px; color: #b0b0d0; line-height: 1.6; }

/* AI 综合投资建议（折叠式） */
.ap-ai-summary {
  background: #16162a;
  border: 1px solid #2a2a4a;
  border-left: 3px solid #5a7af0;
  border-radius: 6px;
  overflow: hidden;
}
.ap-summary-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #b0b0d0;
  user-select: none;
}
.ap-summary-toggle:hover { background: rgba(255,255,255,0.03); }
.ap-summary-svg {
  color: #606080;
  transition: transform 0.2s;
  vertical-align: middle;
}
.ap-summary-svg.is-expanded { transform: rotate(180deg); }
.ap-summary-body {
  padding: 0 14px 12px;
  font-size: 13px;
  color: #c0c0d8;
  line-height: 1.7;
}

/* Markdown 渲染样式 */
.md-content :deep(h1),
.md-content :deep(h2),
.md-content :deep(h3) {
  font-size: 13px;
  font-weight: 600;
  color: #d8d8f0;
  margin: 10px 0 4px 0;
}
.md-content :deep(h1) { font-size: 14px; }
.md-content :deep(strong) {
  color: #e8e8ff;
  font-weight: 600;
}
.md-content :deep(p) {
  margin: 4px 0;
  color: #c0c0d8;
}
.md-content :deep(ul),
.md-content :deep(ol) {
  padding-left: 16px;
  margin: 3px 0;
}
.md-content :deep(li) {
  margin: 2px 0;
  color: #c0c0d8;
}
.md-content :deep(em) {
  color: #a0a0c0;
  font-style: italic;
}
.md-content :deep(code) {
  background: #22223a;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  color: #d0a0f0;
}
</style>
