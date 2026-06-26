<template>
  <div class="ra-result">
    <el-card shadow="never" class="ra-result-header">
      <div class="ra-result-title">
        <div class="title-left">
          <span class="title-icon">✨</span>
          <h3>智能分析报告</h3>
        </div>
        <div class="title-tags">
          <el-tag type="info" effect="plain" round class="meta-tag">
            <el-icon><Timer /></el-icon> 耗时 {{ result.elapsed_seconds?.toFixed(1) }}s
          </el-tag>
          <el-tag type="success" effect="light" round class="meta-tag">
            <el-icon><Filter /></el-icon> 提取 {{ result.candidate_count }} 只候选标的
          </el-tag>
        </div>
        <div class="title-actions">
          <el-button type="primary" plain round :icon="Download" @click="$emit('export-report')">导出完整简报</el-button>
          <el-button round :icon="Close" @click="$emit('clear-result')" class="close-btn">关闭视图</el-button>
        </div>
      </div>
    </el-card>

    <div class="ra-tabs-container">
      <el-collapse v-model="activeNames" class="ra-collapse">
        <!-- 主题分析 -->
        <el-collapse-item name="chain">
          <template #title>
            <span class="tab-label"><el-icon><Connection /></el-icon> 供应链主题分析</span>
          </template>
          <div class="tab-content-wrapper">
            <el-table 
              :data="result.chain_view" 
              stripe 
              size="default" 
              :default-sort="{ prop: 'theme_score', order: 'descending' }"
              :header-cell-style="{ background: 'var(--el-fill-color-light)' }"
            >
              <el-table-column prop="sector" label="归属板块" width="120">
                <template #default="{ row }">
                  <span class="sector-text">{{ row.sector }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="link" label="提取主题 / 产业链环节" min-width="200">
                <template #default="{ row }">
                  <span class="theme-text">{{ row.link }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="theme_score" label="研报共识热度" width="140" sortable align="center">
                <template #default="{ row }">
                  <el-progress 
                    :percentage="row.theme_score" 
                    :color="row.theme_score >= 60 ? 'var(--el-color-danger)' : row.theme_score >= 40 ? 'var(--el-color-warning)' : 'var(--text-muted)'"
                    :stroke-width="8"
                    :show-text="false"
                    style="width: 60px; display: inline-block; vertical-align: middle; margin-right: 8px"
                  />
                  <span class="score-text">{{ row.theme_score }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="judgment" label="供需判断" width="120" align="center">
                <template #default="{ row }">
                  <el-tag
                    :type="row.judgment === 'tight' ? 'danger' : row.judgment === 'mixed' ? 'warning' : 'success'"
                    effect="light"
                    round
                  >
                    {{ row.judgment === 'tight' ? '🔥 供给紧缺' : row.judgment === 'mixed' ? '⚡ 供需平衡' : '❄️ 供给过剩' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="frequency" label="研报提及频次" width="130" sortable align="center">
                <template #default="{ row }">
                  <span class="freq-text">{{ row.frequency }} 次</span>
                </template>
              </el-table-column>
              <el-table-column prop="confidence" label="AI置信度" width="100" align="center">
                <template #default="{ row }">
                  <span class="confidence-text">{{ row.confidence }}%</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-collapse-item>

        <!-- 主题热度图 -->
        <el-collapse-item name="heatmap">
          <template #title>
            <span class="tab-label"><el-icon><DataAnalysis /></el-icon> 瓶颈热度矩阵图</span>
          </template>
          <div class="tab-content-wrapper">
            <div ref="heatmapRef" style="width:100%;height:550px" />
          </div>
        </el-collapse-item>

        <!-- 候选标的 -->
        <el-collapse-item name="candidates">
          <template #title>
            <span class="tab-label"><el-icon><DataLine /></el-icon> 精选标的池 ({{ result.candidates?.length || 0 }})</span>
          </template>
          <div class="tab-content-wrapper">
            <el-table 
              :data="result.candidates" 
              stripe 
              size="default" 
              :default-sort="{ prop: 'score', order: 'descending' }"
              :header-cell-style="{ background: 'var(--el-fill-color-light)' }"
            >
              <el-table-column type="index" label="#" width="50" align="center" />
              <el-table-column label="股票名称/代码" width="160">
                <template #default="{ row }">
                  <div class="stock-info">
                    <span class="stock-name">{{ row.name }}</span>
                    <span class="stock-code">{{ row.code }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="score" label="综合评分" width="110" sortable align="center">
                <template #default="{ row }">
                  <div class="score-badge" :class="row.score >= 80 ? 'score-high' : row.score >= 60 ? 'score-mid' : 'score-low'">
                    {{ row.score }}
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="score_label" label="AI评级" width="100" align="center">
                <template #default="{ row }">
                  <el-tag size="small" effect="dark" :type="row.score_label === 'strong_buy' ? 'danger' : row.score_label === 'buy' ? 'warning' : 'info'">
                    {{ row.score_label === 'strong_buy' ? '强推' : row.score_label === 'buy' ? '推荐' : '中性' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="roe" label="ROE" width="90" sortable align="center">
                <template #default="{ row }">
                  <span class="num-text">{{ row.roe?.toFixed(1) }}%</span>
                </template>
              </el-table-column>
              <el-table-column prop="pe" label="PE" width="80" sortable align="center">
                <template #default="{ row }">
                  <span class="num-text">{{ row.pe?.toFixed(1) || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="industry" label="细分行业" width="120" show-overflow-tooltip />
              <el-table-column label="现价" width="90" align="right" sortable>
                <template #default="{ row }">
                  <span class="price-text" v-if="row.current_price">{{ row.current_price.toFixed(2) }}</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="距52周高" width="100" align="right" sortable>
                <template #default="{ row }">
                  <span class="pct-text" v-if="row.pct_from_52w_high != null" :class="row.pct_from_52w_high > -10 ? 'is-up' : 'is-down'">
                    {{ row.pct_from_52w_high > 0 ? '+' : '' }}{{ row.pct_from_52w_high }}%
                  </span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="异动信号" width="110" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.score_conflict" size="small" type="danger" effect="plain">⚠ 评分冲突</el-tag>
                  <el-tag v-else-if="row.monitor_signal" size="small" effect="plain" :type="row.monitor_signal === 'strong_buy' || row.monitor_signal === 'buy' ? 'danger' : row.monitor_signal === 'sell' || row.monitor_signal === 'strong_sell' ? 'success' : 'info'">
                    实时: {{ row.monitor_signal }}
                  </el-tag>
                  <span v-else class="text-muted">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="sectors" label="覆盖板块" min-width="160">
                <template #default="{ row }">
                  <div class="tag-list">
                    <el-tag v-for="s in row.sectors" :key="s" size="small" type="info" effect="plain">{{ s }}</el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120" align="center" fixed="right">
                <template #default="{ row }">
                  <div class="action-btns">
                    <el-tooltip content="加入自选" placement="top">
                      <el-button size="small" circle :icon="Star" @click="$emit('add-to-watchlist', row)" />
                    </el-tooltip>
                    <el-tooltip content="价格行为分析" placement="top">
                      <el-button size="small" circle type="primary" plain :icon="TrendCharts" @click="$emit('price-action-jump', row)" />
                    </el-tooltip>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-collapse-item>

        <!-- 研报简报 -->
        <el-collapse-item name="report">
          <template #title>
            <span class="tab-label"><el-icon><Document /></el-icon> AI研报摘要</span>
          </template>
          <div class="tab-content-wrapper report-wrapper">
            <div v-if="result.report_md" class="md-content" v-html="renderMd(result.report_md)" />
            <el-empty v-else description="暂无研报摘要内容" :image-size="100" />
          </div>
        </el-collapse-item>

        <!-- 板块详情 -->
        <el-collapse-item name="details">
          <template #title>
            <span class="tab-label"><el-icon><Warning /></el-icon> 抓取日志</span>
          </template>
          <div class="tab-content-wrapper details-wrapper">
            <el-descriptions 
              v-for="(det, sec) in result.sector_details || {}" 
              :key="sec" 
              :title="`板块：${sec}`" 
              :column="2" 
              border 
              class="detail-desc"
            >
              <el-descriptions-item label="数据来源">
                <el-tag size="small" effect="plain">{{ det.source }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="研报解析数量">
                <span class="highlight-num">{{ det.report_count }}</span> 份
              </el-descriptions-item>
              <el-descriptions-item v-if="det.error" label="异常状态" :span="2">
                <el-alert :title="det.error" type="error" :closable="false" />
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Download, Star, TrendCharts, Close, Timer, Filter, Connection, DataAnalysis, DataLine, Document, Warning } from '@element-plus/icons-vue'
import { renderMd } from '@/utils/markdown'
import type { AnalysisResult } from '@/api/researchAnalysis'
import * as echarts from 'echarts'

const props = defineProps<{
  result: AnalysisResult
  activeTab: string
}>()

const emit = defineEmits<{
  (e: 'update:activeTab', val: string): void
  (e: 'export-report'): void
  (e: 'clear-result'): void
  (e: 'add-to-watchlist', row: any): void
  (e: 'price-action-jump', row: any): void
}>()

const activeNames = ref(['chain', 'heatmap', 'candidates', 'report', 'details'])

const heatmapRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let resizeObs: ResizeObserver | null = null

function renderHeatmap() {
  nextTick(() => {
    if (!heatmapRef.value) return
    if (!chartInstance) {
      chartInstance = echarts.init(heatmapRef.value)
    }

    const items = props.result.chain_view || []
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
            return `${d.name}<br/>瓶颈分数: ${d.value}<br/>供需判断: ${d.data?.judgment === 'tight' ? '热门' : d.data?.judgment === 'mixed' ? '一般' : '冷门'}`
          },
        },
        grid: { left: '14%', right: '8%', top: 10, bottom: 30 },
        xAxis: { type: 'value', name: '热度分数', max: 100 },
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
            return `${sec}<br/>${d.name}<br/>热度分数: ${d.value}<br/>判断: ${d.data?.judgment === 'tight' ? '热门' : d.data?.judgment === 'mixed' ? '一般' : '冷门'}`
          },
        },
      })
    }
  })
}

watch(() => props.result, (val) => {
  if (val && val.chain_view?.length && activeNames.value.includes('heatmap')) {
    renderHeatmap()
  }
}, { deep: true })

watch(() => activeNames.value, (val) => {
  if (val.includes('heatmap')) {
    setTimeout(() => { renderHeatmap() }, 100)
  }
})

onMounted(() => {
  if (heatmapRef.value) {
    resizeObs = new ResizeObserver(() => { chartInstance?.resize() })
    resizeObs.observe(heatmapRef.value)
  }
  if (activeNames.value.includes('heatmap')) {
    renderHeatmap()
  }
})

onUnmounted(() => {
  resizeObs?.disconnect()
  chartInstance?.dispose()
})
</script>

<style scoped>
.ra-result {
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: slideUp 0.4s ease-out forwards;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.ra-result-header {
  border-radius: 16px;
  border: none;
  box-shadow: 0 4px 16px var(--bg-hover-subtle);
  background: var(--bg-card);
  overflow: hidden;
}
.ra-result-header :deep(.el-card__body) {
  padding: 20px 24px;
}

.ra-result-title { 
  display: flex; 
  align-items: center; 
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}
.title-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title-icon {
  font-size: 24px;
}
.title-left h3 { 
  margin: 0; 
  font-size: 18px; 
  font-weight: 600;
  color: var(--el-text-color-primary); 
}
.title-tags {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}
.meta-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 12px;
  height: 28px;
}
.title-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ra-tabs-container {
  background: var(--bg-card);
  border-radius: 16px;
  box-shadow: 0 4px 16px var(--bg-hover-subtle);
  overflow: hidden;
}

.ra-collapse {
  border: none;
}

.ra-collapse :deep(.el-collapse-item__header) {
  background: var(--el-fill-color-light);
  padding: 0 16px;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid var(--border-color);
}

.ra-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.tab-label {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab-content-wrapper {
  padding: 20px;
  background: var(--bg-card);
}

.sector-text {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.theme-text {
  color: var(--el-text-color-regular);
}
.score-text {
  font-weight: bold;
  color: var(--el-text-color-primary);
}
.freq-text {
  color: var(--el-text-color-secondary);
}
.confidence-text {
  font-family: Monaco, Consolas, monospace;
  color: var(--el-text-color-regular);
}

.stock-info {
  display: flex;
  flex-direction: column;
}
.stock-name {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.stock-code {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.score-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-weight: bold;
  font-size: 13px;
}
.score-high {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}
.score-mid {
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning);
}
.score-low {
  background: var(--el-color-info-light-9);
  color: var(--el-color-info);
}

.num-text, .price-text {
  font-family: Monaco, Consolas, monospace;
}
.pct-text {
  font-family: Monaco, Consolas, monospace;
  font-weight: 600;
}
.is-up { color: var(--el-color-danger); }
.is-down { color: var(--el-color-success); }

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.action-btns {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.report-wrapper {
  max-width: 900px;
  margin: 0 auto;
}
.details-wrapper {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.detail-desc {
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
  border-radius: 8px;
  overflow: hidden;
}
.highlight-num {
  font-size: 16px;
  font-weight: bold;
  color: var(--el-color-primary);
}

.md-content { line-height: 1.8; font-size: 15px; padding: 0 8px; color: var(--el-text-color-primary); }
.md-content :deep(h1) { font-size: 22px; margin: 24px 0 12px; }
.md-content :deep(h2) { font-size: 18px; margin: 20px 0 10px; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 8px; color: var(--el-color-primary); }
.md-content :deep(h3) { font-size: 16px; margin: 16px 0 8px; }
.md-content :deep(ul) { padding-left: 24px; }
.md-content :deep(li) { margin: 6px 0; }
.md-content :deep(strong) { color: var(--el-text-color-primary); font-weight: 600; }
.md-content :deep(hr) { margin: 24px 0; border: none; border-top: 1px solid var(--el-border-color-lighter); }
</style>