<template>
  <div class="research-page">
    <!-- 顶部控制区 -->
    <el-card shadow="never" class="ra-head">
      <div class="ra-head-inner">
        <div class="ra-head-left">
          <h2>投资研报分析</h2>
          <p class="subtitle">供应链视角的板块研报聚合与标的筛选</p>
        </div>
        <div class="ra-head-right">
          <el-button :icon="Refresh" @click="loadHistory">刷新历史</el-button>
        </div>
      </div>

      <el-divider style="margin: 12px 0" />

      <div class="ra-controls">
        <div class="ra-sector-select">
          <span class="label">行业板块：</span>
          <el-checkbox-group v-model="selectedSectors" size="small">
            <el-checkbox-button v-for="s in presetSectors" :key="s" :value="s" :label="s">
              {{ s }}
            </el-checkbox-button>
          </el-checkbox-group>
        </div>
        <div class="ra-actions">
          <el-input-number v-model="topN" :min="5" :max="50" size="small" controls-position="right" />
          <span class="label" style="margin-left:4px">候选数</span>
          <el-button
            type="primary"
            :icon="MagicStick"
            :loading="running"
            :disabled="selectedSectors.length === 0"
            @click="startAnalysis"
          >
            {{ running ? '分析中...' : '开始分析' }}
          </el-button>
        </div>
      </div>

      <!-- 进度条 -->
      <div v-if="running" class="ra-progress">
        <el-progress
          :percentage="taskProgress"
          :stroke-width="14"
          striped
          striped-flow
          :status="taskStatus === 'failed' ? 'exception' : undefined"
        />
        <div class="ra-progress-row">
          <p class="ra-progress-msg">{{ taskMessage }}</p>
          <el-button v-if="taskId && taskStatus === 'processing'" size="small" type="danger" plain @click="cancelAnalysis">取消</el-button>
        </div>
      </div>
    </el-card>

    <!-- 历史记录 -->
    <el-card v-if="!currentResult" shadow="never" class="ra-history">
      <el-tabs v-model="historyTab">
        <el-tab-pane label="分析记录" name="history">
          <div v-if="history.length === 0" class="empty-state">
            <el-empty description="暂无分析记录，请选择一个行业板块开始" />
          </div>
          <el-table
            v-else
            :data="history"
            stripe
            size="small"
            highlight-current-row
            @row-click="viewHistory"
          >
            <el-table-column prop="created_at" label="时间" width="170" />
            <el-table-column prop="sectors" label="板块" width="200">
              <template #default="{ row }">
                <el-tag v-for="s in row.sectors" :key="s" size="small" style="margin-right:4px">{{ s }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="result.candidate_count" label="候选标的" width="90" align="center" />
            <el-table-column prop="result.elapsed_seconds" label="耗时(s)" width="90" align="center">
              <template #default="{ row }">
                {{ row.result?.elapsed_seconds?.toFixed(1) || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center">
              <template #default="{ row }">
                <el-button v-if="row.task_id" size="small" text :icon="Download" @click.stop="exportHistory(row.task_id, row.sectors)" />
              </template>
            </el-table-column>
            <el-table-column prop="result.sector_details" label="数据来源" min-width="160">
              <template #default="{ row }">
                <span v-for="(det, sec) in row.result?.sector_details || {}" :key="sec">
                  {{ sec }}: {{ det.source }} ({{ det.report_count }})&nbsp;
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 分析结果 -->
    <div v-if="currentResult" class="ra-result">
      <el-card shadow="never" class="ra-result-header">
        <div class="ra-result-title">
          <h3>分析结果</h3>
          <el-tag type="success" effect="dark" size="small">
            耗时 {{ currentResult.elapsed_seconds?.toFixed(1) }}s
          </el-tag>
          <el-tag>{{ currentResult.candidate_count }} 只候选</el-tag>
          <el-button size="small" :icon="Download" @click="exportReport">导出简报</el-button>
          <el-button size="small" @click="clearResult" style="margin-left:auto">关闭</el-button>
        </div>
      </el-card>

      <el-tabs v-model="resultTab" class="ra-tabs">
        <!-- 主题分析 -->
        <el-tab-pane label="主题分析" name="chain">
          <el-card shadow="never">
            <el-table :data="currentResult.chain_view" stripe border size="small" :default-sort="{ prop: 'theme_score', order: 'descending' }">
              <el-table-column prop="sector" label="板块" width="100" />
              <el-table-column prop="link" label="主题" min-width="180" />
              <el-table-column prop="theme_score" label="热度" width="110" sortable align="center">
                <template #default="{ row }">
                  <el-tag
                    :type="row.theme_score >= 60 ? 'danger' : row.theme_score >= 40 ? 'warning' : 'info'"
                    effect="dark"
                  >
                    {{ row.theme_score }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="judgment" label="热度判断" width="110" align="center">
                <template #default="{ row }">
                  <el-tag
                    :type="row.judgment === 'tight' ? 'danger' : row.judgment === 'mixed' ? 'warning' : 'success'"
                    size="small"
                  >
                    {{ row.judgment === 'tight' ? '热门' : row.judgment === 'mixed' ? '一般' : '冷门' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="frequency" label="提及频次" width="100" sortable align="center" />
              <el-table-column prop="confidence" label="置信度" width="90" align="center" />
            </el-table>
          </el-card>
        </el-tab-pane>

        <!-- 主题热度图 -->
        <el-tab-pane label="主题热度图" name="heatmap">
          <el-card shadow="never">
            <div ref="heatmapRef" style="width:100%;height:500px" />
          </el-card>
        </el-tab-pane>

        <!-- 候选标的 -->
        <el-tab-pane label="候选标的" name="candidates">
          <el-card shadow="never">
            <el-table :data="currentResult.candidates" stripe border size="small" :default-sort="{ prop: 'score', order: 'descending' }">
              <el-table-column type="index" label="#" width="50" />
              <el-table-column prop="code" label="代码" width="100" />
              <el-table-column prop="name" label="名称" width="120" />
              <el-table-column prop="score" label="评分" width="90" sortable align="center">
                <template #default="{ row }">
                  <el-tag
                    :type="row.score >= 80 ? 'danger' : row.score >= 60 ? 'warning' : 'info'"
                    effect="dark"
                  >
                    {{ row.score }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="score_label" label="标签" width="100" align="center">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.score_label === 'strong_buy' ? 'danger' : row.score_label === 'buy' ? 'warning' : 'info'">
                    {{ row.score_label }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="roe" label="ROE" width="80" sortable align="center">
                <template #default="{ row }">{{ row.roe?.toFixed(1) }}%</template>
              </el-table-column>
              <el-table-column prop="pe" label="PE" width="80" sortable align="center" />
              <el-table-column prop="industry" label="行业" width="120" />
              <el-table-column label="现价" width="90" align="center" sortable>
                <template #default="{ row }">
                  <span v-if="row.current_price">¥{{ row.current_price.toFixed(2) }}</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="距52周高" width="90" align="center" sortable>
                <template #default="{ row }">
                  <span v-if="row.pct_from_52w_high != null" :style="{ color: row.pct_from_52w_high > -10 ? '#f56c6c' : '#67c23a' }">{{ row.pct_from_52w_high > 0 ? '+' : '' }}{{ row.pct_from_52w_high }}%</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="距200日均" width="90" align="center" sortable>
                <template #default="{ row }">
                  <span v-if="row.pct_from_ma200 != null" :style="{ color: row.pct_from_ma200 > 20 ? '#f56c6c' : '#67c23a' }">{{ row.pct_from_ma200 > 0 ? '+' : '' }}{{ row.pct_from_ma200 }}%</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="监控信号" width="100" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.score_conflict" size="small" type="danger" effect="dark">⚠冲突</el-tag>
                  <el-tag v-else-if="row.monitor_signal" size="small" :type="row.monitor_signal === 'strong_buy' || row.monitor_signal === 'buy' ? 'danger' : row.monitor_signal === 'sell' || row.monitor_signal === 'strong_sell' ? 'success' : 'info'">
                    {{ row.monitor_signal }}
                  </el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="PA信号" width="80" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.pa_signal" size="small" :type="row.pa_signal === 'BUY_SETUP' ? 'danger' : 'success'">{{ row.pa_signal === 'BUY_SETUP' ? '买入' : '卖出' }}</el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column prop="mention_count" label="提及次数" width="90" sortable align="center" />
              <el-table-column prop="sectors" label="覆盖板块" min-width="150">
                <template #default="{ row }">
                  <el-tag v-for="s in row.sectors" :key="s" size="small" style="margin:1px 2px">{{ s }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="140" align="center" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" text :icon="Star" @click="addToWatchlist(row)" />
                  <el-tooltip content="价格行为学择时分析" placement="top">
                    <el-button size="small" text :icon="TrendCharts" @click="priceActionJump(row)" />
                  </el-tooltip>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <!-- 研报简报 -->
        <el-tab-pane label="研报简报" name="report">
          <el-card shadow="never">
            <div v-if="currentResult.report_md" class="md-content" v-html="renderMd(currentResult.report_md)" />
            <el-empty v-else description="暂无简报内容" />
          </el-card>
        </el-tab-pane>

        <!-- 板块详情 -->
        <el-tab-pane label="板块详情" name="details">
          <el-card shadow="never">
            <el-descriptions v-for="(det, sec) in currentResult.sector_details || {}" :key="sec" :title="sec" :column="2" border style="margin-bottom:16px">
              <el-descriptions-item label="数据来源">{{ det.source }}</el-descriptions-item>
              <el-descriptions-item label="研报数量">{{ det.report_count }}</el-descriptions-item>
              <el-descriptions-item v-if="det.error" label="错误" :span="2">
                <el-tag type="danger">{{ det.error }}</el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick, Refresh, Download, Star, TrendCharts } from '@element-plus/icons-vue'
import { researchApi, type AnalysisResult, type HistoryItem } from '@/api/researchAnalysis'
import { watchlistApi } from '@/api/watchlist'
import { renderMd } from '@/utils/markdown'
import * as echarts from 'echarts'

const selectedSectors = ref<string[]>([])
const presetSectors = ref<string[]>([])
const topN = ref(10)
const running = ref(false)
const taskId = ref('')
const taskStatus = ref('')
const taskProgress = ref(0)
const taskMessage = ref('')
const historyTab = ref('history')
const resultTab = ref('chain')
const history = ref<HistoryItem[]>([])
const currentResult = ref<AnalysisResult | null>(null)
const heatmapRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

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

// 渲染瓶颈热力图
function renderHeatmap(result: AnalysisResult) {
  nextTick(() => {
    if (!heatmapRef.value) return
    if (!chartInstance) {
      chartInstance = echarts.init(heatmapRef.value)
    }

    const items = result.chain_view || []
    if (!items.length) { chartInstance.clear(); return }

    // 按板块分组，每板块内按分数排序
    const groups: Record<string, any[]> = {}
    items.forEach(v => {
      if (!groups[v.sector]) groups[v.sector] = []
      groups[v.sector].push(v)
    })
    const sectorNames = Object.keys(groups).sort()
    for (const s of sectorNames) groups[s].sort((a, b) => b.theme_score - a.theme_score)

    if (sectorNames.length === 1) {
      // 单板块 → 水平柱状图
      const arr = groups[sectorNames[0]]
      chartInstance.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: (p: any) => {
            const d = p[0]
            return `${d.name}<br/>瓶颈分数: ${d.value}<br/>供需判断: ${d.data?.judgment === 'tight' ? '紧缺' : d.data?.judgment === 'mixed' ? '混合' : '过剩'}`
          },
        },
        grid: { left: '14%', right: '8%', top: 10, bottom: 30 },
        xAxis: { type: 'value', name: '瓶颈分数', max: 100 },
        yAxis: { type: 'category', data: arr.map(v => v.link), axisLabel: { fontSize: 11 }, inverse: true },
        series: [{
          type: 'bar', data: arr.map(v => ({
            value: v.theme_score,
            itemStyle: { color: v.theme_score >= 70 ? '#c53929' : v.theme_score >= 40 ? '#e69d3c' : '#7bc96f' },
            judgment: v.judgment,
          })),
          barMaxWidth: 22,
          label: { show: true, position: 'right', fontSize: 10, formatter: (p: any) => `${p.value}分` },
        }],
      })
    } else {
      // 多板块 → 每个板块独立柱状图，用 grid 分块排布
      const n = sectorNames.length
      const cols = Math.min(n, 3)
      const rows = Math.ceil(n / cols)
      const wPct = 100 / cols
      const hPct = 100 / rows

      // 收集所有板块的最长 link 名，计算左留白
      const maxLinkLen = Math.max(...sectorNames.map(s =>
        Math.max(...groups[s].map(v => v.link.length))
      ))

      const series: any[] = []
      const grid: any[] = []

      sectorNames.forEach((s, i) => {
        const col = i % cols
        const row = Math.floor(i / cols)
        const gIdx = i

        grid.push({
          left: `${col * wPct + 1}%`,
          top: `${row * hPct + 2}%`,
          right: `${100 - (col + 1) * wPct + 0.5}%`,
          bottom: `${100 - (row + 1) * hPct + 4}%`,
          containLabel: true,
        })

        const arr = groups[s]
        series.push({
          type: 'bar',
          gridIndex: gIdx,
          xAxisIndex: gIdx,
          yAxisIndex: gIdx,
          data: arr.map(v => ({
            value: v.theme_score,
            itemStyle: { color: v.theme_score >= 70 ? '#c53929' : v.theme_score >= 40 ? '#e69d3c' : '#7bc96f' },
            judgment: v.judgment,
          })),
          barMaxWidth: 16,
          label: { show: true, position: 'right', fontSize: 9, formatter: (p: any) => `${p.value}分` },
        })
      })

      const xAxes = sectorNames.map((_, i) => ({
        type: 'value', max: 100, axisLabel: { show: false }, splitLine: { show: false },
        gridIndex: i,
      }))
      const yAxes = sectorNames.map((s, i) => ({
        type: 'category', data: groups[s].map(v => v.link), inverse: true,
        axisLabel: { fontSize: 10 },
        gridIndex: i,
      }))

      // Add sector title on top: use a custom render or just put it in the grid top label
      // ECharts doesn't support per-grid titles, so use a graphic layer
      const topOffset = 20 / rows
      const graphic = sectorNames.map((s, i) => {
        const col = i % cols
        const row = Math.floor(i / cols)
        return {
          type: 'text',
          left: `${col * wPct + 2}%`,
          top: `${row * hPct + 0.5}%`,
          style: {
            text: `【${s}】`,
            fontSize: 13,
            fontWeight: 'bold',
          },
        }
      })

      chartInstance.setOption({
        grid, xAxis: xAxes, yAxis: yAxes, series, graphic,
        tooltip: {
          trigger: 'axis',
          formatter: (p: any) => {
            if (!p || !p[0]) return ''
            const d = p[0]
            const sec = sectorNames[d.seriesIndex]
            return `${sec}<br/>${d.name}<br/>瓶颈分数: ${d.value}<br/>供需判断: ${d.data?.judgment === 'tight' ? '紧缺' : d.data?.judgment === 'mixed' ? '混合' : '过剩'}`
          },
        },
      })
    }
  })
}

// 结果变化时更新热力图
watch(() => currentResult.value, (val) => {
  if (val && val.chain_view?.length) {
    renderHeatmap(val)
  }
})

watch(() => resultTab.value, (val) => {
  if (val === 'heatmap' && currentResult.value) {
    setTimeout(() => { if (currentResult.value) renderHeatmap(currentResult.value) }, 100)
  }
})

// 窗口缩放时自适应
let resizeObs: ResizeObserver | null = null
onMounted(() => {
  loadSectors()
  loadHistory()
  if (heatmapRef.value) {
    resizeObs = new ResizeObserver(() => { chartInstance?.resize() })
    resizeObs.observe(heatmapRef.value)
  }
})

onUnmounted(() => {
  stopPolling()
  resizeObs?.disconnect()
  chartInstance?.dispose()
})
</script>

<style scoped>
.research-page { padding: 16px; }

.ra-head { margin-bottom: 16px; }
.ra-head-inner { display: flex; justify-content: space-between; align-items: flex-start; }
.ra-head-left h2 { margin: 0; font-size: 18px; }
.subtitle { margin: 4px 0 0; font-size: 13px; color: var(--text-secondary, #909399); }

.ra-controls { display: flex; flex-direction: column; gap: 12px; }
.ra-sector-select { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ra-sector-select .label { font-size: 13px; color: var(--text-secondary, #909399); white-space: nowrap; }
.ra-actions { display: flex; align-items: center; gap: 8px; }

.ra-progress { margin-top: 16px; }
.ra-progress-row { display: flex; align-items: center; justify-content: space-between; margin-top: 6px; }
.ra-progress-msg { font-size: 12px; color: var(--text-secondary, #909399); }

.ra-history { margin-bottom: 16px; }
.empty-state { padding: 40px 0; }

.ra-result-header { margin-bottom: 0; }
.ra-result-title { display: flex; align-items: center; gap: 8px; }
.ra-result-title h3 { margin: 0; font-size: 16px; }

.ra-tabs { margin-top: 16px; }

.md-content { line-height: 1.8; font-size: 14px; padding: 0 8px; }
.md-content :deep(h1) { font-size: 20px; margin: 16px 0 8px; }
.md-content :deep(h2) { font-size: 17px; margin: 14px 0 6px; border-bottom: 1px solid var(--border-color, #ebeef5); padding-bottom: 4px; }
.md-content :deep(h3) { font-size: 15px; margin: 12px 0 4px; }
.md-content :deep(ul) { padding-left: 20px; }
.md-content :deep(li) { margin: 4px 0; }
.md-content :deep(strong) { color: var(--text-primary, #303133); }
.md-content :deep(hr) { margin: 16px 0; border: none; border-top: 1px solid var(--border-color, #ebeef5); }
</style>
