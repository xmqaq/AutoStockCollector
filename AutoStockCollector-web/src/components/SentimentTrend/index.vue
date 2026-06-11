<template>
  <div class="sentiment-trend">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="header-toolbar">
          <span>舆情趋势分析</span>
          <el-radio-group v-model="timeRange" size="small">
            <el-radio-button label="1W">近1周</el-radio-button>
            <el-radio-button label="1M">近1月</el-radio-button>
            <el-radio-button label="3M">近3月</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      
      <div class="sentiment-overview">
        <div class="overview-score">
          <div class="score-value" :class="getScoreClass(currentScore)">
            {{ currentScore }}
          </div>
          <div class="score-label">舆情指数</div>
        </div>
        <div class="overview-details">
          <div class="detail-item">
            <span class="detail-label">正面新闻</span>
            <span class="detail-value rise">{{ sentimentStats.positive }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">中性新闻</span>
            <span class="detail-value">{{ sentimentStats.neutral }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">负面新闻</span>
            <span class="detail-value fall">{{ sentimentStats.negative }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">关注度</span>
            <span class="detail-value">{{ sentimentStats.attention }}</span>
          </div>
        </div>
      </div>
      
      <v-chart :option="sentimentOption" style="height: 280px" autoresize />
    </el-card>
    
    <el-card shadow="never" class="section-card">
      <template #header>
        <span>事件驱动信号</span>
      </template>
      <div class="events-timeline">
        <div 
          v-for="(event, idx) in events" 
          :key="idx"
          :class="['event-item', event.type]"
        >
          <div class="event-marker">
            <div class="marker-dot"></div>
            <div class="marker-line" v-if="idx < events.length - 1"></div>
          </div>
          <div class="event-content">
            <div class="event-header">
              <span class="event-date">{{ event.date }}</span>
              <el-tag size="small" :type="getEventType(event.type)">
                {{ event.typeLabel }}
              </el-tag>
            </div>
            <div class="event-title">{{ event.title }}</div>
            <div class="event-desc">{{ event.description }}</div>
            <div class="event-impact">
              <span>影响:</span>
              <el-rate v-model="event.impact" disabled size="small" />
            </div>
          </div>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="section-card">
      <template #header>
        <span>关键词云</span>
      </template>
      <div class="keywords-cloud">
        <div 
          v-for="(kw, idx) in keywords" 
          :key="idx"
          :class="['keyword-item', getKeywordClass(kw.weight)]"
          :style="{ fontSize: getKeywordSize(kw.weight) + 'px' }"
        >
          {{ kw.word }}
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { getChartTheme as ct } from '@/utils/chartTheme'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkPointComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, GridComponent, TooltipComponent, MarkPointComponent, CanvasRenderer])

const timeRange = ref('1M')
const currentScore = ref(68)

const sentimentStats = computed(() => ({
  positive: 45,
  neutral: 32,
  negative: 12,
  attention: '高',
}))

const mockSentimentData = computed(() => {
  const result = []
  let score = 60
  for (let i = 0; i < 30; i++) {
    const date = new Date()
    date.setDate(date.getDate() - (30 - i))
    score += (Math.random() - 0.5) * 10
    score = Math.max(20, Math.min(90, score))
    result.push({
      date: date.toISOString().split('T')[0],
      score: Math.round(score),
    })
  }
  return result
})

const sentimentOption = computed(() => {
  const data = mockSentimentData.value
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: ct().tooltipBg,
      borderColor: ct().tooltipBorder,
      textStyle: { color: ct().tooltipText },
      formatter: (params: unknown[]) => {
        const p = params[0] as { axisValue: string; value: number }
        const score = p.value
        const color = score >= 60 ? '#67c23a' : score >= 40 ? '#e6a23c' : '#f56c6c'
        return `<div style="padding:8px">
          <div style="font-weight:bold;color:${ct().tooltipText}">${p.axisValue}</div>
          <div style="color:${color}">舆情指数: ${score}</div>
        </div>`
      },
    },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date),
      axisLine: { lineStyle: { color: ct().axisLineColor } },
      axisLabel: { color: ct().textColor, fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLine: { lineStyle: { color: ct().axisLineColor } },
      splitLine: { lineStyle: { color: ct().splitLineColor, type: 'dashed' } },
      axisLabel: { color: ct().textColor },
    },
    series: [{
      type: 'line',
      data: data.map(d => d.score),
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(103,194,58,0.4)' },
            { offset: 0.5, color: 'rgba(230,162,60,0.2)' },
            { offset: 1, color: 'rgba(245,108,108,0)' },
          ],
        },
      },
      markLine: {
        silent: true,
        data: [
          { yAxis: 60, lineStyle: { color: '#67c23a', type: 'dashed' }, label: { formatter: '偏正面', color: '#67c23a' } },
          { yAxis: 40, lineStyle: { color: '#f56c6c', type: 'dashed' }, label: { formatter: '偏负面', color: '#f56c6c' } },
        ],
      },
    }],
  }
})

const events = ref([
  { date: '2024-01-20', type: 'positive', typeLabel: '利好', title: '业绩预增公告', description: '公司发布业绩预告，预计全年净利润增长50%', impact: 4 },
  { date: '2024-01-15', type: 'neutral', typeLabel: '中性', title: '行业政策发布', description: '行业相关政策出台，对公司影响中性', impact: 2 },
  { date: '2024-01-10', type: 'negative', typeLabel: '利空', title: '高管减持', description: '高管计划减持不超过1%股份', impact: 3 },
  { date: '2024-01-05', type: 'positive', typeLabel: '利好', title: '订单公告', description: '重大订单落地，合同金额超预期', impact: 5 },
])

const keywords = ref([
  { word: '业绩', weight: 95 },
  { word: '增长', weight: 85 },
  { word: '订单', weight: 75 },
  { word: '突破', weight: 65 },
  { word: '合作', weight: 55 },
  { word: '研发', weight: 50 },
  { word: '市场', weight: 45 },
  { word: '扩张', weight: 40 },
])

function getScoreClass(score: number): string {
  if (score >= 60) return 'score-high'
  if (score >= 40) return 'score-mid'
  return 'score-low'
}

function getEventType(type: string): string {
  switch (type) {
    case 'positive': return 'success'
    case 'negative': return 'danger'
    default: return 'info'
  }
}

function getKeywordClass(weight: number): string {
  if (weight >= 80) return 'keyword-high'
  if (weight >= 50) return 'keyword-mid'
  return 'keyword-low'
}

function getKeywordSize(weight: number): number {
  return 12 + (weight / 10)
}
</script>

<style scoped>
.sentiment-trend {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sentiment-overview {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  padding: 16px;
  background: var(--border-color);
  border-radius: 8px;
}

.overview-score {
  text-align: center;
  padding: 16px 24px;
  background: rgba(103, 194, 58, 0.1);
  border-radius: 8px;
}

.score-value {
  font-size: 36px;
  font-weight: 600;
}

.score-high { color: #67c23a; }
.score-mid { color: #e6a23c; }
.score-low { color: #f56c6c; }

.score-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.overview-details {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 11px;
  color: var(--text-muted);
}

.detail-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-value.rise { color: #67c23a; }
.detail-value.fall { color: #f56c6c; }

.events-timeline {
  display: flex;
  flex-direction: column;
}

.event-item {
  display: flex;
  gap: 16px;
  padding-bottom: 16px;
}

.event-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 20px;
}

.marker-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #409eff;
  flex-shrink: 0;
}

.event-item.positive .marker-dot { background: #67c23a; }
.event-item.negative .marker-dot { background: #f56c6c; }

.marker-line {
  flex: 1;
  width: 2px;
  background: var(--border-color);
  margin-top: 4px;
}

.event-content {
  flex: 1;
  background: var(--border-color);
  border-radius: 8px;
  padding: 12px;
}

.event-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.event-date {
  font-size: 11px;
  color: var(--text-muted);
}

.event-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.event-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  margin-bottom: 8px;
}

.event-impact {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.keywords-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  padding: 20px;
}

.keyword-item {
  padding: 8px 16px;
  border-radius: 16px;
  cursor: pointer;
  transition: transform 0.2s;
}

.keyword-item:hover {
  transform: scale(1.1);
}

.keyword-high {
  background: rgba(103, 194, 58, 0.2);
  color: #67c23a;
  font-weight: 600;
}

.keyword-mid {
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
}

.keyword-low {
  background: var(--border-color);
  color: var(--text-muted);
}

.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}
</style>