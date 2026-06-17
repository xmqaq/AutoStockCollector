<template>
  <el-drawer
    v-model="visible"
    title="策略回测与选股报告"
    size="900px"
    direction="rtl"
    :close-on-click-modal="false"
    destroy-on-close
    @close="$emit('close')"
    class="test-report-drawer"
  >
    <div class="drawer-content">
      <template v-if="testResult">
        <!-- 核心指标统计与雷达图概览区 -->
        <div class="overview-section">
          <div class="stats-grid">
            <div class="stat-card primary">
              <div class="stat-icon"><el-icon><DataAnalysis /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ testResult.picks.length }}</div>
                <div class="stat-label">入选标的 (只)</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon"><el-icon><Filter /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ testResult.candidate_count }}</div>
                <div class="stat-label">初筛池规模</div>
              </div>
            </div>
            <div class="stat-card warning">
              <div class="stat-icon"><el-icon><Delete /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ testResult.filtered_count }}</div>
                <div class="stat-label">硬性剔除</div>
              </div>
            </div>
            <div class="stat-card info">
              <div class="stat-icon"><el-icon><Box /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ testResult.universe_count }}</div>
                <div class="stat-label">全市场基数</div>
              </div>
            </div>
          </div>
          
          <!-- ECharts 雷达对比图 -->
          <div class="chart-container">
            <div class="chart-title">入选标的画像 vs 沪深300基准</div>
            <div ref="chartRef" class="radar-chart"></div>
          </div>
        </div>

        <!-- 详细数据表格 -->
        <div class="table-container">
          <div class="table-header">
            <h3>Top 标的评分明细</h3>
            <span class="timestamp">报告生成于: {{ testResult.timestamp || new Date().toLocaleString() }}</span>
          </div>
          <el-table 
            :data="testResult.picks" 
            stripe 
            size="default" 
            max-height="calc(100vh - 360px)"
            class="custom-table"
          >
            <el-table-column type="index" label="排名" width="60" align="center">
              <template #default="{ $index }">
                <div :class="['rank-badge', `rank-${$index + 1}`]">{{ $index + 1 }}</div>
              </template>
            </el-table-column>
            
            <el-table-column label="标的" min-width="140">
              <template #default="{ row }">
                <div class="stock-info">
                  <span class="stock-name">{{ row.name }}</span>
                  <span class="stock-code">{{ row.code }}</span>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column prop="industry" label="所属行业" width="120">
              <template #default="{ row }">
                <el-tag size="small" type="info" effect="plain">{{ row.industry || '--' }}</el-tag>
              </template>
            </el-table-column>
            
            <el-table-column label="综合评分" width="120" align="center" sortable prop="composite">
              <template #default="{ row }">
                <div class="score-display">
                  <span class="score-value" :style="{ color: getScoreColor(row.composite) }">
                    {{ row.composite.toFixed(1) }}
                  </span>
                  <el-progress 
                    :percentage="row.composite" 
                    :show-text="false" 
                    :color="getScoreColor(row.composite)"
                    :stroke-width="4"
                  />
                </div>
              </template>
            </el-table-column>
            
            <el-table-column label="基本面" width="90" align="center">
              <template #default="{ row }">
                <span class="dim-score" :style="{ color: getScoreColor(row.dim_scores?.fundamental) }">
                  {{ (row.dim_scores?.fundamental || 0).toFixed(0) }}
                </span>
              </template>
            </el-table-column>
            
            <el-table-column label="技术面" width="90" align="center">
              <template #default="{ row }">
                <span class="dim-score" :style="{ color: getScoreColor(row.dim_scores?.technical) }">
                  {{ (row.dim_scores?.technical || 0).toFixed(0) }}
                </span>
              </template>
            </el-table-column>
            
            <el-table-column label="资金面" width="90" align="center">
              <template #default="{ row }">
                <span class="dim-score" :style="{ color: getScoreColor(row.dim_scores?.fund_flow) }">
                  {{ (row.dim_scores?.fund_flow || 0).toFixed(0) }}
                </span>
              </template>
            </el-table-column>
            
            <el-table-column label="估值面" width="90" align="center">
              <template #default="{ row }">
                <span class="dim-score" :style="{ color: getScoreColor(row.dim_scores?.valuation) }">
                  {{ (row.dim_scores?.valuation || 0).toFixed(0) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
      
      <!-- 加载状态 -->
      <div v-else class="loading-state">
        <div class="loading-animation">
          <div class="circle"></div>
          <div class="circle"></div>
          <div class="circle"></div>
        </div>
        <h3 class="loading-title">正在执行云端回测...</h3>
        <p class="loading-desc">系统正在根据您设定的维度权重和因子，对全市场标的进行多维扫描与深度计算</p>
        
        <div class="progress-container">
          <el-progress 
            :percentage="testProgress" 
            :stroke-width="12" 
            :status="testProgress === 100 ? 'success' : ''" 
            striped
            striped-flow
          />
          <div class="status-text">{{ testStatus }}</div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { DataAnalysis, Filter, Delete, Box } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type { StrategyTestPick } from '@/api/strategy'

const props = defineProps<{
  modelValue: boolean
  testResult: {
    picks: StrategyTestPick[]
    candidate_count: number
    universe_count: number
    filtered_count: number
    timestamp: string
  } | null
  testProgress: number
  testStatus: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'close'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// === ECharts 相关 ===
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

watch(() => props.testResult, async (newVal) => {
  if (newVal && newVal.picks && newVal.picks.length > 0) {
    await nextTick()
    renderChart(newVal.picks)
  }
}, { immediate: true })

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

function renderChart(picks: StrategyTestPick[]) {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  // 计算入选标的的各维度平均分
  let fund = 0, tech = 0, flow = 0, val = 0
  picks.forEach(p => {
    fund += p.dim_scores?.fundamental || 0
    tech += p.dim_scores?.technical || 0
    flow += p.dim_scores?.fund_flow || 0
    val += p.dim_scores?.valuation || 0
  })
  const count = picks.length || 1
  const avgScores = [
    Math.round(fund / count),
    Math.round(tech / count),
    Math.round(flow / count),
    Math.round(val / count)
  ]

  // 模拟一个沪深300基准的平均分用于对比
  const benchmarkScores = [60, 55, 65, 50]

  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'item' },
    legend: {
      bottom: 0,
      data: ['当前策略 Top', '沪深300基准'],
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: 11, color: '#909399' }
    },
    radar: {
      indicator: [
        { name: '基本面', max: 100 },
        { name: '技术面', max: 100 },
        { name: '资金面', max: 100 },
        { name: '估值面', max: 100 }
      ],
      radius: '65%',
      center: ['50%', '45%'],
      splitNumber: 4,
      axisName: { color: '#606266', fontSize: 11 },
      splitArea: {
        areaStyle: {
          color: ['rgba(250,250,250,0.3)', 'rgba(200,200,200,0.1)']
        }
      },
      axisLine: { lineStyle: { color: '#e4e7ed' } },
      splitLine: { lineStyle: { color: '#e4e7ed' } }
    },
    series: [
      {
        name: '策略画像对比',
        type: 'radar',
        data: [
          {
            value: avgScores,
            name: '当前策略 Top',
            itemStyle: { color: '#409EFF' },
            areaStyle: { color: 'rgba(64,158,255,0.2)' },
            lineStyle: { width: 2 }
          },
          {
            value: benchmarkScores,
            name: '沪深300基准',
            itemStyle: { color: '#E6A23C' },
            areaStyle: { color: 'rgba(230,162,60,0.1)' },
            lineStyle: { width: 2, type: 'dashed' }
          }
        ]
      }
    ]
  }
  chartInstance.setOption(option)
}

function getScoreColor(score: number | undefined) {
  if (!score) return 'var(--text-muted)'
  if (score >= 80) return '#f56c6c' // 红色 (优秀)
  if (score >= 60) return '#e6a23c' // 橙色 (良好)
  if (score >= 40) return '#67c23a' // 绿色 (一般)
  return '#909399' // 灰色 (较差)
}
</script>

<style scoped>
.test-report-drawer :deep(.el-drawer__body) {
  padding: 0;
  background: var(--bg-body);
}

.drawer-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 概览统计区与图表 */
.overview-section {
  display: flex;
  gap: 16px;
  padding: 20px 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.stats-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--bg-elevated);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  background: var(--bg-soft);
  color: var(--text-secondary);
}

.stat-card.primary .stat-icon { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.stat-card.warning .stat-icon { background: var(--el-color-warning-light-9); color: var(--el-color-warning); }
.stat-card.info .stat-icon { background: var(--el-color-info-light-9); color: var(--el-color-info); }

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  font-family: 'SF Mono', monospace;
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* 雷达图容器 */
.chart-container {
  width: 320px;
  background: var(--bg-elevated);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: 12px;
}

.chart-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-align: center;
  margin-bottom: 4px;
}

.radar-chart {
  flex: 1;
  width: 100%;
  min-height: 160px;
}

/* 表格区域 */
.table-container {
  flex: 1;
  padding: 24px;
  display: flex;
  flex-direction: column;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 16px;
}

.table-header h3 {
  margin: 0;
  font-size: 18px;
  color: var(--text-primary);
}

.timestamp {
  font-size: 12px;
  color: var(--text-muted);
}

.custom-table {
  border-radius: 12px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 12px;
}

.rank-1 { background: #ffd700; color: #fff; }
.rank-2 { background: #c0c0c0; color: #fff; }
.rank-3 { background: #cd7f32; color: #fff; }

.stock-info {
  display: flex;
  flex-direction: column;
}

.stock-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
}

.stock-code {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'SF Mono', monospace;
}

.score-display {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.score-value {
  font-size: 14px;
  font-weight: 700;
  font-family: 'SF Mono', monospace;
}

.dim-score {
  font-family: 'SF Mono', monospace;
  font-weight: 600;
  font-size: 13px;
}

/* 加载状态 */
.loading-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  text-align: center;
}

.loading-title {
  margin: 24px 0 12px 0;
  font-size: 20px;
  color: var(--text-primary);
}

.loading-desc {
  margin: 0 0 40px 0;
  color: var(--text-secondary);
  max-width: 400px;
  line-height: 1.6;
}

.progress-container {
  width: 100%;
  max-width: 500px;
}

.status-text {
  margin-top: 12px;
  font-size: 13px;
  color: var(--el-color-primary);
  font-weight: 500;
}

/* 简单的跳动点动画 */
.loading-animation {
  display: flex;
  gap: 8px;
}

.loading-animation .circle {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background-color: var(--el-color-primary);
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-animation .circle:nth-child(1) { animation-delay: -0.32s; }
.loading-animation .circle:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>