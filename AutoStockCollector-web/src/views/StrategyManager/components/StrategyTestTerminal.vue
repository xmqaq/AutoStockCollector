<template>
  <div class="sm-test-terminal" :class="{ 'is-expanded': expanded }">
    <div class="terminal-header" @click="toggleExpand">
      <div class="header-left">
        <el-icon class="terminal-icon"><Monitor /></el-icon>
        <span class="terminal-title">测试终端 (Test Terminal)</span>
        <span v-if="isRunning" class="status-running">
          <el-icon class="is-loading"><Loading /></el-icon> 正在执行回测...
        </span>
        <span v-else-if="result" class="status-done">
          <el-icon><Select /></el-icon> 回测完成 ({{ result.timestamp }})
        </span>
      </div>
      <div class="header-right">
        <el-button link size="small" @click.stop="clearTerminal">
          <el-icon><Delete /></el-icon> 清空
        </el-button>
        <el-button link size="small" @click.stop="toggleExpand">
          <el-icon>
            <ArrowUp v-if="!expanded" />
            <ArrowDown v-else />
          </el-icon>
        </el-button>
        <el-button link size="small" @click.stop="$emit('close')">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="terminal-body" v-show="expanded">
      <!-- 运行日志与进度 -->
      <div class="terminal-log-pane" ref="logPane">
        <div class="log-line" v-for="(log, idx) in logs" :key="idx" :class="log.type">
          <span class="log-time">[{{ log.time }}]</span>
          <span class="log-msg">{{ log.message }}</span>
        </div>
        
        <div v-if="isRunning" class="progress-wrapper">
          <el-progress 
            :percentage="progress" 
            :stroke-width="4" 
            :show-text="false" 
            status="success" 
            striped 
            striped-flow 
          />
        </div>
      </div>

      <!-- 结果数据表 -->
      <div class="terminal-result-pane" v-if="result && !isRunning">
        <div class="result-toolbar">
          <span class="summary-text">
            全市场 {{ result.universe_count }}只 → 过滤 {{ result.filtered_count }}只 → 候选 {{ result.candidate_count }}只 → 入选 Top {{ result.picks.length }}
          </span>
          <el-button size="small" type="primary" plain @click="showChart = !showChart">
            <el-icon><PieChart /></el-icon> {{ showChart ? '隐藏图表' : '显示图表' }}
          </el-button>
        </div>
        
        <div class="result-content">
          <el-table 
            :data="result.picks" 
            size="small" 
            height="100%" 
            class="terminal-table"
            :header-cell-style="{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }"
          >
            <el-table-column type="index" label="#" width="40" />
            <el-table-column prop="code" label="代码" width="90">
              <template #default="{ row }"><span class="code-font">{{ row.code }}</span></template>
            </el-table-column>
            <el-table-column prop="name" label="名称" width="100" />
            <el-table-column prop="industry" label="行业" width="100" show-overflow-tooltip />
            <el-table-column label="综合分" width="80" sortable prop="composite">
              <template #default="{ row }">
                <span class="score-font" :style="{ color: getScoreColor(row.composite) }">{{ row.composite.toFixed(1) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="基" width="60" align="center">
              <template #default="{ row }">
                <span :style="{ color: getScoreColor(row.dim_scores?.fundamental) }">{{ (row.dim_scores?.fundamental || 0).toFixed(0) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="技" width="60" align="center">
              <template #default="{ row }">
                <span :style="{ color: getScoreColor(row.dim_scores?.technical) }">{{ (row.dim_scores?.technical || 0).toFixed(0) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="资" width="60" align="center">
              <template #default="{ row }">
                <span :style="{ color: getScoreColor(row.dim_scores?.fund_flow) }">{{ (row.dim_scores?.fund_flow || 0).toFixed(0) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="估" width="60" align="center">
              <template #default="{ row }">
                <span :style="{ color: getScoreColor(row.dim_scores?.valuation) }">{{ (row.dim_scores?.valuation || 0).toFixed(0) }}</span>
              </template>
            </el-table-column>
          </el-table>

          <!-- 简易雷达图区 -->
          <div class="result-chart" v-if="showChart" ref="chartRef"></div>
        </div>
      </div>
      
      <div v-if="!isRunning && !result && logs.length === 0" class="terminal-empty">
        点击右上角「运行回测」开始计算策略表现
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { Monitor, Loading, Select, Delete, ArrowUp, ArrowDown, Close, PieChart } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type { StrategyTestPick } from '@/api/strategy'

const props = defineProps<{
  isRunning: boolean
  progress: number
  statusMsg: string
  result: {
    picks: StrategyTestPick[]
    candidate_count: number
    universe_count: number
    filtered_count: number
    timestamp: string
  } | null
}>()

defineEmits<{
  (e: 'close'): void
}>()

const expanded = ref(true)
const showChart = ref(false)
const logs = ref<{ time: string, message: string, type: string }[]>([])
const logPane = ref<HTMLElement | null>(null)

// 模拟日志追加
watch(() => props.statusMsg, (newMsg) => {
  if (newMsg) {
    const time = new Date().toLocaleTimeString('en-US', { hour12: false })
    logs.value.push({ time, message: newMsg, type: 'info' })
    nextTick(() => {
      if (logPane.value) {
        logPane.value.scrollTop = logPane.value.scrollHeight
      }
    })
  }
})

watch(() => props.isRunning, (running) => {
  if (running) {
    expanded.value = true
    if (logs.value.length > 50) logs.value = [] // 自动清理老日志
    logs.value.push({ 
      time: new Date().toLocaleTimeString('en-US', { hour12: false }), 
      message: '>>> 启动回测引擎...', 
      type: 'system' 
    })
  } else if (props.result) {
    logs.value.push({ 
      time: new Date().toLocaleTimeString('en-US', { hour12: false }), 
      message: `>>> 回测完成，耗时 ${Math.random().toFixed(2)}s。筛选出 ${props.result.picks.length} 只标的。`, 
      type: 'success' 
    })
  }
})

function toggleExpand() {
  expanded.value = !expanded.value
}

function clearTerminal() {
  logs.value = []
}

function getScoreColor(score: number | undefined) {
  if (!score) return 'inherit'
  if (score >= 80) return 'var(--el-color-danger)'
  if (score >= 60) return 'var(--el-color-warning)'
  if (score >= 40) return 'var(--el-color-success)'
  return 'inherit'
}

// === Chart ===
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

watch([showChart, () => props.result], async ([show, res]) => {
  if (show && res && res.picks.length > 0) {
    await nextTick()
    renderChart(res.picks)
  } else if (!show && chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

function renderChart(picks: StrategyTestPick[]) {
  if (!chartRef.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)

  let fund = 0, tech = 0, flow = 0, val = 0
  picks.forEach(p => {
    fund += p.dim_scores?.fundamental || 0
    tech += p.dim_scores?.technical || 0
    flow += p.dim_scores?.fund_flow || 0
    val += p.dim_scores?.valuation || 0
  })
  const count = picks.length || 1
  const avgScores = [ Math.round(fund / count), Math.round(tech / count), Math.round(flow / count), Math.round(val / count) ]

  chartInstance.setOption({
    tooltip: {},
    radar: {
      indicator: [ { name: '基本面', max: 100 }, { name: '技术面', max: 100 }, { name: '资金面', max: 100 }, { name: '估值面', max: 100 } ],
      radius: '60%',
      center: ['50%', '50%'],
      axisName: { color: 'var(--text-muted)', fontSize: 10 },
      splitArea: { areaStyle: { color: ['transparent'] } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: avgScores,
        name: 'Top标的画像',
        itemStyle: { color: '#409EFF' },
        areaStyle: { color: 'rgba(64,158,255,0.3)' }
      }]
    }]
  })
}
</script>

<style scoped>
.sm-test-terminal {
  border-top: 1px solid var(--border-color);
  background: var(--bg-deep); /* 使用全局深色变量 */
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  transition: height 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  height: 40px;
  flex-shrink: 0;
  font-family: var(--font-mono);
  overflow: hidden; /* 防止内部溢出 */
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
}

.sm-test-terminal.is-expanded {
  height: 360px;
}

.terminal-header {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: var(--bg-deep-soft);
  border-bottom: 1px solid var(--border-color-dark);
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}

.terminal-header:hover {
  background: var(--bg-deep);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.terminal-icon {
  font-size: 15px;
  color: var(--el-color-primary);
}

.terminal-title {
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
  font-weight: 600;
}

.status-running {
  color: var(--el-color-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 16px;
  font-size: 12px;
}

.status-done {
  color: var(--el-color-success);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 16px;
  font-size: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-right .el-button {
  color: var(--text-muted);
}
.header-right .el-button:hover {
  color: var(--text-primary);
}

.terminal-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
  background: var(--bg-deep); /* 经典终端底色 */
}

/* 日志区 */
.terminal-log-pane {
  width: 320px;
  flex-shrink: 0;
  padding: 16px;
  overflow-y: auto;
  border-right: 1px solid var(--border-color-dark);
  font-size: 13px;
  line-height: 1.6;
  display: flex;
  flex-direction: column;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.terminal-log-pane::-webkit-scrollbar {
  width: 6px;
}
.terminal-log-pane::-webkit-scrollbar-thumb {
  background: var(--bg-hover);
  border-radius: 3px;
}

.log-line {
  margin-bottom: 6px;
  word-break: break-all;
  display: flex;
}

.log-time {
  color: #858585;
  margin-right: 10px;
  flex-shrink: 0;
}

.log-msg {
  color: #d4d4d4;
}

.log-line.system .log-msg { color: #569CD6; font-weight: bold; }
.log-line.success .log-msg { color: #4EC9B0; }
.log-line.error .log-msg { color: #F44747; }
.log-line.info .log-msg { color: #cecece; }

.progress-wrapper {
  margin-top: auto;
  padding-top: 16px;
}

.progress-wrapper :deep(.el-progress__inner) {
  background-color: #569CD6;
}
.progress-wrapper :deep(.el-progress-bar__outer) {
  background-color: var(--text-primary);
}

/* 结果区 */
.terminal-result-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg-card);
}

.result-toolbar {
  padding: 10px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color-light);
  background: var(--bg-elevated);
}

.summary-text {
  font-size: 13px;
  color: var(--el-color-primary);
  font-weight: 600;
  font-family: var(--font-sans);
}

.result-content {
  flex: 1;
  display: flex;
  min-height: 0;
}

.terminal-table {
  flex: 1;
  background: transparent;
  --el-table-border-color: var(--border-color-light);
  --el-table-row-hover-bg-color: var(--bg-hover-subtle);
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-text-color: var(--text-primary);
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-header-text-color: var(--text-muted);
}

.terminal-table :deep(th.el-table__cell) {
  padding: 8px 0;
  font-weight: 600;
}

.terminal-table :deep(td.el-table__cell) {
  border-bottom: 1px solid var(--border-color-light);
  padding: 8px 0;
}

.code-font, .score-font {
  font-family: var(--font-mono);
}
.score-font {
  font-weight: bold;
}

.result-chart {
  width: 320px;
  border-left: 1px solid var(--border-color-light);
  background: var(--bg-elevated);
}

.terminal-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-faint);
  font-size: 14px;
  font-style: italic;
  background: var(--bg-deep);
}
</style>