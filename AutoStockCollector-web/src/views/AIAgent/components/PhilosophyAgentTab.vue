<template>
  <div class="philosophy-tab" v-loading="philosophyLoading">
    <div class="split-layout">
      <!-- 左侧：流派列表 -->
      <div class="left-sidebar">
        <div class="sidebar-header">
          <span>投资哲学流派</span>
          <el-tag size="small" type="info" round>{{ philosophyAgents.length }}</el-tag>
        </div>
        <div class="school-list">
          <div
            v-for="agent in philosophyAgents"
            :key="agent.agent_id"
            :class="['school-item', { active: selectedAgent?.agent_id === agent.agent_id }]"
            @click="selectAgent(agent)"
          >
            <div class="item-header">
              <span class="name">{{ agent.name }}</span>
              <el-tag size="small" :type="schoolTagType(agent.archetype)" effect="plain">
                {{ schoolLabel(agent.archetype) }}
              </el-tag>
            </div>
            <div class="item-meta">
              <span>周期: {{ holdingLabel(agent.holding_horizon) }}</span>
              <el-divider direction="vertical" />
              <span>风控: <span :class="riskClass(agent.risk_tolerance)">{{ (agent.risk_tolerance * 100).toFixed(0) }}%</span></span>
            </div>
          </div>
          <el-empty v-if="philosophyAgents.length === 0 && !philosophyLoading" description="暂无数据" :image-size="60" />
        </div>
      </div>

      <!-- 右侧：详情与可视化 -->
      <div class="right-content">
        <template v-if="selectedAgent">
          <div class="detail-header">
            <div class="title-area">
              <h2>{{ selectedAgent.name }}</h2>
              <span class="agent-id">{{ selectedAgent.agent_id }}</span>
            </div>
            <div class="param-tags">
              <el-tag size="small" type="info">Temp: {{ selectedAgent.temperature }}</el-tag>
              <el-tag size="small" type="info">Tokens: {{ selectedAgent.max_tokens }}</el-tag>
            </div>
          </div>

          <div class="top-cards">
            <el-card shadow="never" class="desc-card">
              <template #header><div class="card-title">流派理念</div></template>
              <p class="desc-text">{{ selectedAgent.description }}</p>
            </el-card>

            <el-card shadow="never" class="radar-card">
              <template #header><div class="card-title">权重维度分析</div></template>
              <div ref="radarChartRef" class="radar-chart-container"></div>
            </el-card>
          </div>

          <el-card shadow="never" class="prompt-card">
            <template #header><div class="card-title">系统提示词 (System Prompt)</div></template>
            <pre class="prompt-content">{{ selectedAgent.system_prompt }}</pre>
          </el-card>
        </template>
        <div v-else class="empty-state">
          <el-icon :size="48" color="var(--border-color)"><DataAnalysis /></el-icon>
          <p>请在左侧选择一个投资流派查看详情</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, onBeforeUnmount } from 'vue'
import { DataAnalysis } from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { philosophyApi, type PhilosophyAgentDetail } from '@/api/ai'

echarts.use([TitleComponent, TooltipComponent, LegendComponent, RadarChart, CanvasRenderer])

const philosophyAgents = ref<PhilosophyAgentDetail[]>([])
const philosophyLoading = ref(false)
const selectedAgent = ref<PhilosophyAgentDetail | null>(null)

const radarChartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const schoolColors: Record<string, string> = {
  value: 'success', growth: '', technical: 'warning',
  macro: 'danger', quant: 'info', hot_money: 'danger',
  risk: '', sentiment: '',
}
const schoolLabelsMap: Record<string, string> = {
  value: '价值派', growth: '成长派', technical: '技术派',
  macro: '宏观派', quant: '量化派', hot_money: '游资派',
  risk: '风控派', sentiment: '舆情派',
}

function schoolTagType(archetype: string): string {
  return schoolColors[archetype] || 'info'
}
function schoolLabel(archetype: string): string {
  return schoolLabelsMap[archetype] || archetype
}
function holdingLabel(h: string): string {
  return { short: '短期', medium: '中期', long: '长期' }[h] || h
}
function riskClass(r: number): string {
  if (r >= 0.7) return 'risk-high'
  if (r >= 0.4) return 'risk-mid'
  return 'risk-low'
}

async function loadPhilosophyAgents() {
  philosophyLoading.value = true
  try {
    const res = await philosophyApi.listAgents()
    if (res.data?.success && Array.isArray(res.data.data)) {
      philosophyAgents.value = res.data.data
      if (philosophyAgents.value.length > 0) {
        selectAgent(philosophyAgents.value[0])
      }
    }
  } catch {
    philosophyAgents.value = []
  } finally {
    philosophyLoading.value = false
  }
}

function selectAgent(agent: PhilosophyAgentDetail) {
  selectedAgent.value = agent
}

watch(selectedAgent, async (newAgent) => {
  if (newAgent) {
    await nextTick()
    renderRadarChart(newAgent)
  }
})

function renderRadarChart(agent: PhilosophyAgentDetail) {
  if (!radarChartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(radarChartRef.value)
  }

  const dimensions = agent.weight_dimensions || {}
  const keys = Object.keys(dimensions)
  
  if (keys.length === 0) {
    chartInstance.clear()
    return
  }

  const indicator = keys.map(key => ({ name: key, max: 1 }))
  const values = keys.map(key => dimensions[key])

  const option = {
    tooltip: { trigger: 'item' },
    radar: {
      indicator,
      radius: '65%',
      splitNumber: 4,
      axisName: { color: 'var(--text-secondary)', fontSize: 12 },
      splitArea: {
        areaStyle: {
          color: ['rgba(21, 89, 140, 0.02)', 'rgba(21, 89, 140, 0.05)', 'rgba(21, 89, 140, 0.08)', 'rgba(21, 89, 140, 0.11)'],
          shadowColor: 'var(--border-color)',
          shadowBlur: 10
        }
      },
      axisLine: { lineStyle: { color: 'rgba(21, 89, 140, 0.2)' } },
      splitLine: { lineStyle: { color: 'rgba(21, 89, 140, 0.2)' } }
    },
    series: [
      {
        name: '权重配比',
        type: 'radar',
        data: [
          {
            value: values,
            name: agent.name,
            symbol: 'circle',
            symbolSize: 6,
            itemStyle: { color: '#15598c' },
            areaStyle: { color: 'rgba(21, 89, 140, 0.3)' },
            lineStyle: { width: 2 }
          }
        ]
      }
    ]
  }

  chartInstance.setOption(option)
}

function handleResize() {
  chartInstance?.resize()
}

onMounted(() => {
  loadPhilosophyAgents()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style scoped>
.philosophy-tab {
  height: 100%;
  min-height: 500px;
}

.split-layout {
  display: flex;
  height: 100%;
  gap: 20px;
}

/* 左侧列表 */
.left-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-elevated);
}

.school-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.school-item {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--bg-elevated);
}

.school-item:hover {
  background: var(--border-color);
}

.school-item.active {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-5);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.item-header .name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
}

.item-meta {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
}

.risk-high { color: var(--el-color-danger); font-weight: 600; }
.risk-mid { color: var(--el-color-warning); font-weight: 600; }
.risk-low { color: var(--el-color-success); font-weight: 600; }

/* 右侧详情 */
.right-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
  padding-right: 8px;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: var(--bg-card);
  border: 1px dashed var(--border-color);
  border-radius: 12px;
}

.empty-state p {
  margin-top: 16px;
  font-size: 14px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.title-area h2 {
  margin: 0 0 4px 0;
  font-size: 22px;
  color: var(--text-primary);
}

.title-area .agent-id {
  font-size: 13px;
  color: var(--text-muted);
  font-family: monospace;
}

.param-tags {
  display: flex;
  gap: 8px;
}

.top-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.desc-card {
  border-radius: 12px;
  background: var(--bg-card);
}

.desc-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.radar-card {
  border-radius: 12px;
  background: var(--bg-card);
}

.radar-chart-container {
  height: 240px;
  width: 100%;
}

.prompt-card {
  border-radius: 12px;
  background: var(--bg-card);
  flex: 1;
  display: flex;
  flex-direction: column;
}

.prompt-card :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.prompt-content {
  margin: 0;
  font-family: 'SF Mono', Consolas, Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  background: var(--bg-elevated);
  padding: 16px;
  border-radius: 8px;
  overflow-y: auto;
  white-space: pre-wrap;
  flex: 1;
}
</style>
