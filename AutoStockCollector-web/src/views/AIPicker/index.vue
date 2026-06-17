<template>
  <div class="ap-page">
    <AIPickerToolbar
      v-model:top-n="topN"
      v-model:candidate-pool="candidatePool"
      :running="running"
      :loading="loading"
      @run-pick="runPick"
      @load-results="loadResults"
    />

    <!-- 进度条 -->
    <div v-if="progressData.is_running || showDoneTip" class="ap-progress-box">
      <template v-if="progressData.is_running">
        <div class="ap-progress-header">量化选股执行中</div>
        <el-progress :percentage="progressData.progress" :stroke-width="14" :color="'#5a7af0'" />
        <div class="ap-progress-status">{{ progressData.status }}</div>
      </template>
      <template v-else-if="showDoneTip">
        <div class="ap-progress-done">选股完成，结果已更新</div>
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

    <AIPickerTable
      :picks="result?.picks || []"
      :expanded-code="expandedCode"
      @toggle-expand="toggleExpand"
      @go-analysis="goAnalysis"
    />

    <AIPickerDetailPanel
      :pick="expandedPick"
      @close="expandedCode = ''"
    />

    <AIPickerSummary
      :ai-summary="result?.ai_summary"
      v-model:expanded="summaryExpanded"
    />

    <AIPickerTrack
      :track-expanded="trackExpanded"
      :track-loading="trackLoading"
      :track-error="trackError"
      :track="track"
      @toggle-track="toggleTrack"
    />

    <el-empty v-if="!result?.picks?.length && !loading" description="暂无选股结果，点击「立即重跑」" />

    <p v-if="result" class="ap-method-note">评分为运行时快照：K线取近60个交易日，财务取最新报告期，资金面取近5日均值，PE/PB/ROE优先取估值缓存（5分钟刷新）；候选池已剔除ST/次新/低流动性股票</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { aiServiceApi, type AIPickResult, type AIPick, type PickTrackData } from '@/api/ai'

import AIPickerToolbar from './components/AIPickerToolbar.vue'
import AIPickerTable from './components/AIPickerTable.vue'
import AIPickerDetailPanel from './components/AIPickerDetailPanel.vue'
import AIPickerSummary from './components/AIPickerSummary.vue'
import AIPickerTrack from './components/AIPickerTrack.vue'

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
.ap-meta { display: flex; gap: 18px; font-size: 12px; color: var(--text-alt-muted, #909399); }

/* 进度条 */
.ap-progress-box {
  background: var(--bg-card-alt, #ffffff);
  border: 1px solid var(--border-alt, #ebeef5);
  border-radius: 8px;
  padding: 12px 16px;
}
.ap-progress-header { font-size: 13px; color: var(--text-alt-body, #303133); margin-bottom: 8px; }
.ap-progress-status { font-size: 12px; color: var(--text-alt-muted, #909399); margin-top: 6px; }
.ap-progress-done { font-size: 13px; color: #4ade80; text-align: center; padding: 4px 0; }

.ap-method-note { font-size: 11px; color: var(--text-alt-muted, #909399); text-align: center; margin-top: 8px; }
</style>
