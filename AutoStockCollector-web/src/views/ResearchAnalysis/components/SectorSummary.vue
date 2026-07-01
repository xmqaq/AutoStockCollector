<template>
  <div class="sector-summary">
    <div class="summary-toolbar">
      <el-input
        v-model="filterText"
        placeholder="筛选板块名..."
        clearable
        size="small"
        class="filter-input"
        :prefix-icon="Search"
      />
      <span class="summary-meta">
        共 {{ sectorCards.length }} 个板块
        <template v-if="failedCount"> · {{ failedCount }} 个失败</template>
      </span>
    </div>

    <el-empty v-if="sectorCards.length === 0" description="暂无板块分析数据" />

    <div v-else class="sector-grid">
      <div
        v-for="card in filteredCards"
        :key="card.sector"
        :class="['sector-card', { 'is-failed': card.failed }]"
      >
        <div class="card-header">
          <span class="sector-name">{{ card.sector }}</span>
          <div class="header-tags">
            <el-tag v-if="card.sentiment" size="small" effect="dark" :type="sentimentType(card.sentiment)">
              {{ sentimentLabel(card.sentiment) }}
            </el-tag>
            <el-tag size="small" effect="plain" type="info">研报 {{ card.reportCount }}</el-tag>
          </div>
        </div>

        <div v-if="card.failed" class="failed-note">
          <el-icon><Warning /></el-icon>
          <span>分析失败：{{ card.error || '未知原因' }}</span>
        </div>

        <template v-else>
          <!-- 主题热度 Top3 -->
          <div class="card-section">
            <div class="section-title">
              <el-icon><Connection /></el-icon> 主题热度
              <span v-if="card.themes.length === 0" class="muted">无</span>
            </div>
            <div v-for="(t, i) in card.themes" :key="i" class="theme-row">
              <div class="theme-head">
                <span class="theme-link" :title="t.description">{{ t.link }}</span>
                <span :class="['judgment-tag', `jdg-${t.judgment}`]">{{ judgmentLabel(t.judgment) }}</span>
              </div>
              <el-progress
                :percentage="t.theme_score"
                :stroke-width="6"
                :show-text="false"
                :color="scoreColor(t.theme_score)"
              />
              <div class="theme-meta">
                热度 {{ t.theme_score }} · 频次 {{ t.frequency }} · 置信度 {{ t.confidence }}
              </div>
            </div>
          </div>

          <!-- 候选标的 Top3 -->
          <div class="card-section">
            <div class="section-title">
              <el-icon><DataLine /></el-icon> 候选标的
              <span v-if="card.candidates.length === 0" class="muted">无</span>
            </div>
            <div v-for="(c, i) in card.candidates" :key="i" class="cand-row">
              <div class="cand-main">
                <span class="cand-name">{{ c.name }}</span>
                <span class="cand-code">{{ c.code }}</span>
              </div>
              <div class="cand-side">
                <span :class="['score-badge', c.score >= 80 ? 'score-high' : c.score >= 60 ? 'score-mid' : 'score-low']">
                  {{ c.score }}
                </span>
                <el-tag size="small" effect="dark" :type="c.score_label === 'strong_buy' ? 'danger' : c.score_label === 'buy' ? 'warning' : 'info'">
                  {{ c.score_label === 'strong_buy' ? '强推' : c.score_label === 'buy' ? '推荐' : '中性' }}
                </el-tag>
                <el-tooltip content="加入自选" placement="top">
                  <el-button size="small" link :icon="Star" @click="$emit('add-to-watchlist', c)" />
                </el-tooltip>
                <el-tooltip content="价格行为分析" placement="top">
                  <el-button size="small" link type="primary" :icon="TrendCharts" @click="$emit('price-action-jump', c)" />
                </el-tooltip>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, Star, TrendCharts, Connection, DataLine, Warning } from '@element-plus/icons-vue'
import type { AnalysisResult, Candidate, ChainViewItem } from '@/api/researchAnalysis'

const props = defineProps<{ result: AnalysisResult }>()

defineEmits<{
  (e: 'add-to-watchlist', row: Candidate): void
  (e: 'price-action-jump', row: Candidate): void
}>()

const filterText = ref('')

interface SectorCard {
  sector: string
  sentiment: string
  reportCount: number
  themes: ChainViewItem[]
  candidates: Candidate[]
  failed: boolean
  error?: string
}

const sectorCards = computed<SectorCard[]>(() => {
  const r = props.result
  if (!r) return []
  // 板块集合：sector_details 的 key ∪ chain_view/candidates 里出现的 sector ∪ result.sectors
  const sectorSet = new Set<string>()
  Object.keys(r.sector_details || {}).forEach(s => sectorSet.add(s))
  ;(r.chain_view || []).forEach(c => c.sector && sectorSet.add(c.sector))
  ;(r.candidates || []).forEach(c => (c.sectors || []).forEach(s => sectorSet.add(s)))
  ;(r.sectors || []).forEach(s => sectorSet.add(s))

  const failed = new Set(r.failed_sectors || [])
  const cards: SectorCard[] = []
  for (const sector of sectorSet) {
    const detail = r.sector_details?.[sector] || {}
    const themes = (r.chain_view || [])
      .filter(c => c.sector === sector)
      .sort((a, b) => (b.theme_score || 0) - (a.theme_score || 0))
      .slice(0, 3)
    const candidates = (r.candidates || [])
      .filter(c => (c.sectors || []).includes(sector))
      .sort((a, b) => (b.score || 0) - (a.score || 0))
      .slice(0, 3)
    cards.push({
      sector,
      sentiment: detail.sentiment || '',
      reportCount: detail.report_count || 0,
      themes,
      candidates,
      failed: failed.has(sector) || !!detail.error,
      error: detail.error,
    })
  }
  // 失败板块排末尾，其余按研报数降序
  cards.sort((a, b) => {
    if (a.failed !== b.failed) return a.failed ? 1 : -1
    return b.reportCount - a.reportCount
  })
  return cards
})

const filteredCards = computed(() => {
  const q = filterText.value.trim().toLowerCase()
  if (!q) return sectorCards.value
  return sectorCards.value.filter(c => c.sector.toLowerCase().includes(q))
})

const failedCount = computed(() => sectorCards.value.filter(c => c.failed).length)

function sentimentLabel(s: string): string {
  return ({ bullish: '看多', bearish: '看空', neutral: '中性' } as Record<string, string>)[s] || s
}
function sentimentType(s: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  return ({ bullish: 'danger', bearish: 'success', neutral: 'info' } as Record<string, any>)[s] || 'info'
}
function judgmentLabel(j: string): string {
  return ({ tight: '供需偏紧', oversupply: '供过于求', mixed: '供需平衡' } as Record<string, string>)[j] || j
}
function scoreColor(s: number): string {
  if (s >= 80) return '#f56c6c'
  if (s >= 60) return '#e6a23c'
  return '#909399'
}
</script>

<style scoped>
.sector-summary { display: flex; flex-direction: column; gap: 12px; }

.summary-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.filter-input { width: 220px; }
.summary-meta { font-size: 13px; color: var(--text-muted); }

.sector-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.sector-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: box-shadow 0.2s;
}
.sector-card:hover { box-shadow: 0 4px 16px var(--bg-hover-subtle); }
.sector-card.is-failed { opacity: 0.7; background: var(--el-fill-color-light); }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 10px;
}
.sector-name { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.header-tags { display: flex; gap: 6px; }

.card-section { display: flex; flex-direction: column; gap: 8px; }
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
}
.muted { color: var(--text-faint); font-weight: 400; font-size: 12px; }

.theme-row { display: flex; flex-direction: column; gap: 3px; }
.theme-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.theme-link {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.judgment-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
}
.jdg-tight { background: rgba(245,108,108,0.12); color: #f56c6c; }
.jdg-oversupply { background: rgba(17,194,126,0.12); color: #11c27e; }
.jdg-mixed { background: rgba(144,147,153,0.12); color: #909399; }
.theme-meta { font-size: 11px; color: var(--text-faint); }

.cand-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}
.cand-main { display: flex; flex-direction: column; min-width: 0; }
.cand-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.cand-code { font-size: 11px; color: var(--text-faint); font-family: var(--font-mono); }
.cand-side { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }

.score-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
}
.score-high { background: rgba(245,108,108,0.12); color: #f56c6c; }
.score-mid { background: rgba(230,162,60,0.12); color: #e6a23c; }
.score-low { background: rgba(144,147,153,0.12); color: #909399; }

.failed-note {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-color-danger);
  font-size: 13px;
  padding: 8px 0;
}
</style>
