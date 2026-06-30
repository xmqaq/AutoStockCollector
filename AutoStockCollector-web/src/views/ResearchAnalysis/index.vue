<template>
  <div class="research-page">
    <!-- 顶部控制区 -->
    <ResearchHeader
      v-model:selectedSectors="selectedSectors"
      v-model:topN="topN"
      :presetSectors="presetSectors"
      :running="running"
      :taskId="taskId"
      :taskStatus="taskStatus"
      :taskProgress="taskProgress"
      :taskMessage="taskMessage"
      @load-history="loadHistory"
      @load-today="loadToday"
      @start-analysis="startAnalysis"
      @cancel-analysis="cancelAnalysis"
    />

    <!-- 历史记录 -->
    <ResearchHistory
      v-if="!currentResult"
      :history="history"
      @view-history="viewHistory"
      @export-history="exportHistory"
    />

    <!-- 分析结果 -->
    <ResearchResultTabs
      v-if="currentResult"
      :result="currentResult"
      v-model:activeTab="resultTab"
      @export-report="exportReport"
      @clear-result="clearResult"
      @add-to-watchlist="addToWatchlist"
      @price-action-jump="priceActionJump"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { researchApi, type AnalysisResult, type HistoryItem } from '@/api/researchAnalysis'
import { watchlistApi } from '@/api/watchlist'

import ResearchHeader from './components/ResearchHeader.vue'
import ResearchHistory from './components/ResearchHistory.vue'
import ResearchResultTabs from './components/ResearchResultTabs.vue'

const selectedSectors = ref<string[]>([])
const presetSectors = ref<string[]>([])
const topN = ref(10)
const running = ref(false)
const taskId = ref('')
const taskStatus = ref('')
const taskProgress = ref(0)
const taskMessage = ref('')
const resultTab = ref('chain')
const history = ref<HistoryItem[]>([])
const currentResult = ref<AnalysisResult | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null
let todayPollTimer: ReturnType<typeof setInterval> | null = null
let todayPollStart = 0
const TODAY_POLL_INTERVAL = 30000  // 30s 轮询今日精选生成进度
const TODAY_POLL_MAX_MS = 60 * 60 * 1000  // 最长轮询 1 小时

async function loadSectors() {
  try {
    const res = await researchApi.listSectors()
    if (res.data?.success) presetSectors.value = res.data.data.map((s: any) => s.name)
  } catch {
    presetSectors.value = [
      '储能', '人形机器人', '半导体', '新能源汽车', 'AI算力', '创新药', '光伏',
      '军工', '消费电子', '医疗器械', '白酒', '家电', '房地产',
      '银行', '证券', '养殖', '煤炭', '有色金属', '基础化工', '电力',
      '保险', '传媒', '通信', '计算机', '交通运输', '食品饮料', '建筑建材',
    ]
  }
}

async function loadHistory() {
  try {
    const res = await researchApi.getHistory()
    if (res.data?.success) history.value = res.data.data
  } catch { /* ignore */ }
}

async function loadToday() {
  try {
    const res = await researchApi.getToday()
    if (res.data?.success && res.data.data) {
      currentResult.value = res.data.data
      resultTab.value = res.data.data.report_md ? 'report' : 'chain'
      stopTodayPolling()
      ElMessage.success(`今日精选已加载，${res.data.data.candidate_count} 只候选标的`)
    } else if (res.data?.success) {
      const status = res.data.status
      if (status === 'running') {
        // 17:30 后 cron 正在生成，启动轻量轮询直到拿到结果
        ElMessage.info(res.data.message || '今日研报分析正在生成中，将自动刷新')
        startTodayPolling()
      } else if (status === 'failed') {
        stopTodayPolling()
        ElMessage.warning(res.data.message || '今日研报分析生成失败，请手动触发')
      } else {
        ElMessage.info(res.data.message || '今日汇总尚未生成，盘后 17:30 自动运行')
      }
    }
  } catch {
    ElMessage.error('加载今日精选失败')
  }
}

function startTodayPolling() {
  stopTodayPolling()
  todayPollStart = Date.now()
  todayPollTimer = setInterval(async () => {
    // 超过最长轮询时间则停止，避免页面长期空转
    if (Date.now() - todayPollStart > TODAY_POLL_MAX_MS) {
      stopTodayPolling()
      ElMessage.info('今日精选生成耗时较长，请稍后手动刷新')
      return
    }
    try {
      const res = await researchApi.getToday()
      if (res.data?.success && res.data.data) {
        currentResult.value = res.data.data
        resultTab.value = res.data.data.report_md ? 'report' : 'chain'
        stopTodayPolling()
        ElMessage.success(`今日精选已生成，${res.data.data.candidate_count} 只候选标的`)
      } else if (res.data?.status === 'failed') {
        // 后台已失败，停止轮询
        stopTodayPolling()
        ElMessage.warning(res.data.message || '今日研报分析生成失败，请手动触发')
      }
    } catch {
      // 网络错误静默，继续轮询
    }
  }, TODAY_POLL_INTERVAL)
}

function stopTodayPolling() {
  if (todayPollTimer) {
    clearInterval(todayPollTimer)
    todayPollTimer = null
  }
}

async function startAnalysis() {
  if (selectedSectors.value.length === 0) {
    ElMessage.warning('请至少选择一个行业板块')
    return
  }
  running.value = true
  taskProgress.value = 0
  taskMessage.value = '正在提交任务...'
  currentResult.value = null
  resultTab.value = 'chain'

  try {
    const res = await researchApi.run(selectedSectors.value, topN.value)
    if (!res.data?.success) {
      ElMessage.error(res.data?.message || '提交失败')
      running.value = false
      return
    }
    taskId.value = res.data.task_id
    taskMessage.value = '任务已提交，正在分析...'
    startPolling()
  } catch {
    running.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(pollResult, 3000)
}

async function cancelAnalysis() {
  if (!taskId.value) return
  try {
    const res = await researchApi.cancel(taskId.value)
    if (res.data?.success) {
      ElMessage.info('任务已取消')
      stopPolling()
      running.value = false
      taskStatus.value = 'cancelled'
    }
  } catch {
    ElMessage.error('取消失败')
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollResult() {
  if (!taskId.value) return
  try {
    const res = await researchApi.getResult(taskId.value)
    const data = res.data
    if (!data?.success) return

    taskStatus.value = data.status
    taskProgress.value = data.progress
    taskMessage.value = data.message

      if (data.status === 'completed') {
        stopPolling()
        running.value = false
        if (data.data) {
          currentResult.value = data.data
          resultTab.value = data.data.report_md ? 'report' : 'chain'
          ElMessage.success(`分析完成，${data.data.candidate_count} 只候选标的`)
        }
      loadHistory()
    } else if (data.status === 'failed') {
      stopPolling()
      running.value = false
      ElMessage.error(data.message || '分析失败')
    } else if (data.status === 'cancelled') {
      stopPolling()
      running.value = false
    }
  } catch {
    // 网络错误等静默处理
  }
}

function viewHistory(row: HistoryItem) {
  if (row.result) {
    const merged: AnalysisResult = { ...row.result, task_id: row.task_id }
    currentResult.value = merged
    resultTab.value = merged.report_md ? 'report' : 'chain'
  }
}

async function exportHistory(taskId: string, sectors: string[]) {
  try {
    const res = await researchApi.exportReport(taskId)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `研报简报_${sectors?.join('-') || 'unknown'}.md`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}

function clearResult() {
  currentResult.value = null
}

async function exportReport() {
  const taskId = currentResult.value?.task_id
  if (!taskId) {
    ElMessage.warning('无简报可导出')
    return
  }
  try {
    const res = await researchApi.exportReport(taskId)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `研报简报_${currentResult.value?.sectors?.join('-') || 'unknown'}.md`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}

async function addToWatchlist(row: any) {
  try {
    const res = await watchlistApi.addWatchlist({ code: row.code })
    if (res.data?.success) {
      ElMessage.success(`${row.name || row.code} 已加入自选`)
    } else {
      ElMessage.warning(res.data?.message || '添加失败')
    }
  } catch {
    ElMessage.error('添加自选失败')
  }
}

const router = useRouter()

function priceActionJump(row: any) {
  router.push({ path: '/price-action', query: { symbol: row.code } })
}

onMounted(() => {
  loadSectors()
  loadHistory()
  loadToday()  // 默认加载今日 cron 汇总，无则显示历史
})

onUnmounted(() => {
  stopPolling()
  stopTodayPolling()
})
</script>

<style scoped>
.research-page { 
  padding: 24px 32px; 
  display: flex;
  flex-direction: column;
  gap: 24px;
  background-color: var(--el-bg-color-page);
  min-height: 100%;
  max-width: 1600px;
  margin: 0 auto;
}
</style>
