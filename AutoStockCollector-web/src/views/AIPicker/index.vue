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
      <span v-if="result.universe_count">
        全市场 {{ result.universe_count }}
        <template v-if="result.filtered_count"> → 剔除 {{ result.filtered_count }}</template>
        → 候选 {{ result.candidate_count }} → 精选 {{ result.picks.length }}
      </span>
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
      <el-table-column label="操作建议" width="80" align="center">
        <template #default="{ row }">
          <span class="ap-action-tag" :class="actionClass(row)">{{ getAction(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="建议仓位" width="90" align="center">
        <template #default="{ row }">
          <el-tooltip v-if="getPosition(row) !== '--'" content="分散配置，总仓位建议不超过60%" placement="top">
            <span class="ap-position">{{ getPosition(row) }}</span>
          </el-tooltip>
          <span v-else class="ap-na">--</span>
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

    <!-- 历史选股效果（折叠式，首次展开时加载） -->
    <div class="ap-ai-summary ap-track">
      <div class="ap-summary-toggle" @click="toggleTrack">
        <span>📈 历史选股效果 <span class="ap-track-sub">vs 等权全市场基准</span></span>
        <svg class="ap-summary-svg" :class="{ 'is-expanded': trackExpanded }" viewBox="0 0 12 12" width="12" height="12">
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div v-if="trackExpanded" class="ap-track-body">
        <div v-if="trackLoading" class="ap-track-tip">⏳ 正在计算全市场等权基准对比，约需10-20秒...</div>
        <div v-else-if="trackError" class="ap-track-tip">{{ trackError }}</div>
        <template v-else-if="track">
          <div class="ap-track-meta">
            已跟踪 {{ track.runs_count }} 次选股（仅 default 策略）· 入场=选股日(含)后首个收盘价 · 基准=同窗口全市场等权平均收益 · 当日批次需待收盘K线入库后才可评估（显示为 -）
          </div>
          <el-table :data="overallRows" size="small" class="ap-table ap-track-table">
            <el-table-column prop="horizon" label="持有期" width="70" align="center" />
            <el-table-column label="选股收益" width="90" align="center">
              <template #default="{ row }"><span :style="{ color: pctColor(row.avg) }">{{ fmtPct(row.avg) }}</span></template>
            </el-table-column>
            <el-table-column label="胜率" width="70" align="center">
              <template #default="{ row }">{{ row.win_rate != null ? row.win_rate + '%' : '-' }}</template>
            </el-table-column>
            <el-table-column label="市场基准" width="90" align="center">
              <template #default="{ row }"><span :style="{ color: pctColor(row.baseline) }">{{ fmtPct(row.baseline) }}</span></template>
            </el-table-column>
            <el-table-column label="超额收益" width="90" align="center">
              <template #default="{ row }"><span class="ap-track-excess" :style="{ color: pctColor(row.excess) }">{{ fmtPct(row.excess) }}</span></template>
            </el-table-column>
            <el-table-column label="跑赢率" width="70" align="center">
              <template #default="{ row }">{{ row.beat_rate != null ? row.beat_rate + '%' : '-' }}</template>
            </el-table-column>
            <el-table-column prop="n" label="样本" width="60" align="center" />
          </el-table>

          <div class="ap-track-runs-title">最近选股批次</div>
          <el-table :data="track.runs.slice(0, 8)" size="small" class="ap-table ap-track-table">
            <el-table-column label="时间" width="110">
              <template #default="{ row }">{{ fmtTime(row.timestamp) }}</template>
            </el-table-column>
            <el-table-column label="精选/可评估" width="92" align="center">
              <template #default="{ row }">{{ row.picks_count }} / {{ row.evaluated }}</template>
            </el-table-column>
            <el-table-column v-for="h in track.horizons" :key="h" :label="h + '日超额'" width="86" align="center">
              <template #default="{ row }">
                <span :style="{ color: pctColor(row.returns[String(h)]?.excess) }">{{ fmtPct(row.returns[String(h)]?.excess) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </div>

    <el-empty v-if="!result?.picks?.length && !loading" description="暂无选股结果，点击「立即重跑」" />

    <p v-if="result" class="ap-method-note">评分为运行时快照：K线取近60个交易日，财务取最新报告期，资金面取近5日均值，PE/PB/ROE优先取估值缓存（5分钟刷新）；候选池已剔除ST/次新/低流动性股票</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import dayjs from 'dayjs'
import { aiServiceApi, type AIPickResult, type AIPick, type PickTrackData } from '@/api/ai'
import { RISE_COLOR, FALL_COLOR, FLAT_COLOR } from '@/utils/format'

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

// ── 历史选股效果跟踪（首次展开时懒加载）──
const trackExpanded = ref(false)
const trackLoading = ref(false)
const trackError = ref('')
const track = ref<PickTrackData | null>(null)

const overallRows = computed(() => {
  if (!track.value) return []
  return track.value.horizons.map(h => ({
    horizon: `${h}日`,
    ...track.value!.overall[String(h)],
  }))
})

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '-'
  return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
}

function pctColor(v: number | null | undefined): string {
  if (v == null) return FLAT_COLOR
  return v > 0 ? RISE_COLOR : v < 0 ? FALL_COLOR : FLAT_COLOR
}

async function toggleTrack() {
  trackExpanded.value = !trackExpanded.value
  if (trackExpanded.value && !track.value && !trackLoading.value) {
    trackLoading.value = true
    trackError.value = ''
    try {
      const res = await aiServiceApi.pickTrack({ horizons: '1,3,5,10', limit: 50, strategy: 'default' })
      track.value = res.data?.data || null
      if (!track.value) trackError.value = '暂无跟踪数据'
    } catch {
      trackError.value = '加载选股效果失败'
    } finally {
      trackLoading.value = false
    }
  }
}

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

// ── 操作建议 / 建议仓位（基于综合分、风险警告、估值分自动推导）──
function pickHasWarning(pick: AIPick): boolean {
  const details = pick.score_details
  if (!details) return false
  for (const dim of Object.values(details)) {
    const items = (dim as any)?.details
    if (!items) continue
    for (const [k, v] of Object.entries(items)) {
      if (k.endsWith('_warning') && typeof v === 'string' && v) return true
    }
  }
  return false
}

function getAction(pick: AIPick): string {
  const composite = pick.composite ?? pick.scores?.composite ?? 0
  const hasWarning = pickHasWarning(pick)
  const valuation = pick.scores?.valuation ?? 50
  if (hasWarning && composite < 82) return '观望'
  if (valuation <= 20 && composite >= 80) return '谨慎关注'  // 高分但估值极低
  if (composite >= 80 && !hasWarning) return '建议关注'
  if (composite >= 75 && !hasWarning) return '可以关注'
  return '观望'
}

function getPosition(pick: AIPick): string {
  const action = getAction(pick)
  const composite = pick.composite ?? pick.scores?.composite ?? 0
  if (action === '谨慎关注') return '5%以内'
  if (action === '建议关注') return composite >= 80 ? '10-15%' : '5-10%'
  if (action === '可以关注') return '5-10%'
  return '--'  // 观望
}

const ACTION_CLASS: Record<string, string> = {
  '建议关注': 'ap-action-green',
  '可以关注': 'ap-action-lightgreen',
  '谨慎关注': 'ap-action-orange',
  '观望': 'ap-action-gray',
}
function actionClass(pick: AIPick): string {
  return ACTION_CLASS[getAction(pick)] || 'ap-action-gray'
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
        if (!data.is_running) {
          // 完成或后端判定运行已中断（僵尸进度），都停止轮询并恢复按钮
          stopProgressPolling()
          running.value = false
          if (data.progress >= 100) {
            showDoneTip.value = true
            await loadResults()
            setTimeout(() => { showDoneTip.value = false }, 4000)
          } else if (data.status) {
            ElMessage.warning(data.status)
          }
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
.ap-title { font-size: 15px; font-weight: 700; color: var(--text-alt-primary); }
.ap-subtitle { font-size: 12px; color: var(--text-alt-muted); }
.ap-controls { display: flex; gap: 8px; align-items: center; }
.ap-meta { display: flex; gap: 18px; font-size: 12px; color: var(--text-alt-muted); }

/* 表格 */
.ap-table { background: transparent; }
.ap-table :deep(.el-table__row) { height: 42px; }
.ap-table :deep(.el-table__row:hover > td) { background: var(--bg-hover-subtle) !important; }
.ap-row-clickable { cursor: pointer; }
.ap-row-active :deep(td) {
  background: rgba(90,122,240,0.08) !important;
  border-left: 2px solid #5a7af0;
}
.ap-code { color: #5a7af0; cursor: pointer; }
.ap-code:hover { text-decoration: underline; }
.ap-na { color: var(--text-alt-muted); }
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

.ap-action-tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 3px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}
.ap-action-green { color: #3aa856; background: rgba(82,196,26,0.14); }
.ap-action-lightgreen { color: #7cc98a; background: rgba(82,196,26,0.07); }
.ap-action-orange { color: #e8912a; background: rgba(250,173,20,0.14); }
.ap-action-gray { color: var(--text-alt-muted); background: rgba(144,144,152,0.12); }
.ap-position { font-size: 12px; color: #5a7af0; cursor: default; white-space: nowrap; }
.ap-expand-svg {
  color: var(--text-alt-muted);
  transition: transform 0.2s;
  vertical-align: middle;
}
.ap-expand-svg.is-expanded { transform: rotate(180deg); }
.ap-col-expand { overflow: visible !important; }
.ap-method-note { font-size: 11px; color: var(--text-alt-muted); text-align: center; margin-top: 8px; }

/* 进度条 */
.ap-progress-box {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 8px;
  padding: 12px 16px;
}
.ap-progress-header { font-size: 13px; color: var(--text-alt-body); margin-bottom: 8px; }
.ap-progress-status { font-size: 12px; color: var(--text-alt-muted); margin-top: 6px; }
.ap-progress-done { font-size: 13px; color: #4ade80; text-align: center; padding: 4px 0; }

/* 展开详情面板 */
.ap-detail-panel {
  background: var(--bg-card-alt);
  border: 1px solid var(--border-alt);
  border-radius: 8px;
  padding: 14px;
  margin-top: -4px;
}
.ap-detail-header {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 14px; font-weight: 600; color: var(--text-alt-body); margin-bottom: 10px;
}
.ap-detail-body { display: flex; flex-direction: column; gap: 10px; }
.ap-dim-block { background: var(--bg-deep-soft); border-radius: 6px; padding: 10px 12px; }
.ap-dim-title {
  display: flex; align-items: center; gap: 10px; margin-bottom: 8px;
}
.ap-dim-label { font-size: 13px; font-weight: 600; color: var(--text-alt-body); min-width: 48px; }
.ap-dim-bar { flex: 1; max-width: 180px; }
.ap-dim-score { font-size: 13px; font-weight: 600; color: var(--text-alt-primary); }
.ap-dim-weight { font-size: 11px; color: var(--text-alt-muted); }
.ap-dim-contrib { font-size: 11px; color: var(--text-alt-muted); }

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
  background: var(--bg-card-alt);
  border-radius: 4px;
  padding: 7px 10px;
}
.ap-cell-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 3px;
}
.ap-cell-name { font-size: 11px; color: var(--text-alt-muted); }
.ap-cell-ratio { font-size: 11px; font-weight: 600; }
.ap-cell-bottom {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ap-cell-value { font-size: 14px; font-weight: 600; color: var(--text-alt-body); white-space: nowrap; }
.ap-mini-bar {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--bg-hover);
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
.ap-detail-empty { color: var(--text-alt-muted); font-size: 13px; text-align: center; padding: 16px 0; }
.ap-detail-advice { margin-top: 10px; border-top: 1px solid var(--border-alt); padding-top: 10px; }
.ap-advice-label { font-size: 12px; color: var(--text-alt-muted); margin-bottom: 4px; }
.ap-advice-text { font-size: 13px; color: var(--text-alt-body); line-height: 1.6; }

/* AI 综合投资建议（折叠式） */
.ap-ai-summary {
  background: var(--bg-deep-soft);
  border: 1px solid var(--border-alt);
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
  color: var(--text-alt-body);
  user-select: none;
}
.ap-summary-toggle:hover { background: var(--bg-hover-subtle); }
.ap-summary-svg {
  color: var(--text-alt-muted);
  transition: transform 0.2s;
  vertical-align: middle;
}
.ap-summary-svg.is-expanded { transform: rotate(180deg); }
.ap-summary-body {
  padding: 0 14px 12px;
  font-size: 13px;
  color: var(--text-alt-body);
  line-height: 1.7;
}

/* 历史选股效果 */
.ap-track-sub { font-size: 11px; font-weight: 400; color: var(--text-alt-muted); margin-left: 6px; }
.ap-track-body { padding: 0 14px 12px; display: flex; flex-direction: column; gap: 8px; }
.ap-track-tip { font-size: 12px; color: var(--text-alt-muted); padding: 8px 0; }
.ap-track-meta { font-size: 11px; color: var(--text-alt-muted); }
.ap-track-table { font-size: 12px; }
.ap-track-excess { font-weight: 600; }
.ap-track-runs-title { font-size: 12px; font-weight: 600; color: var(--text-alt-body); margin-top: 4px; }

/* Markdown 渲染样式 */
.md-content :deep(h1),
.md-content :deep(h2),
.md-content :deep(h3) {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-alt-primary);
  margin: 10px 0 4px 0;
}
.md-content :deep(h1) { font-size: 14px; }
.md-content :deep(strong) {
  color: var(--text-alt-primary);
  font-weight: 600;
}
.md-content :deep(p) {
  margin: 4px 0;
  color: var(--text-alt-body);
}
.md-content :deep(ul),
.md-content :deep(ol) {
  padding-left: 16px;
  margin: 3px 0;
}
.md-content :deep(li) {
  margin: 2px 0;
  color: var(--text-alt-body);
}
.md-content :deep(em) {
  color: var(--text-alt-body);
  font-style: italic;
}
.md-content :deep(code) {
  background: var(--bg-card-alt);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  color: #d0a0f0;
}
</style>
