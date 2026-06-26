<template>
  <div class="sentiment-page">
    <!-- Stats -->
    <div class="stats-bar">
      <el-card shadow="never" class="stat-card stat-bullish">
        <div class="stat-label">利好新闻</div>
        <div class="stat-value">{{ newsFeedPositive.length }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card stat-bearish">
        <div class="stat-label">利空新闻</div>
        <div class="stat-value">{{ newsFeedNegative.length }}</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">涉及股票</div>
        <div class="stat-value">{{ signalsWithNewsCount }}</div>
      </el-card>
    </div>

    <!-- Filter -->
    <div class="filter-bar">
      <el-input
        v-model="localNewsSearchText"
        placeholder="搜索新闻标题/股票代码"
        clearable
        size="small"
        class="search-input"
      />
    </div>

    <!-- Positive News -->
    <div class="sentiment-group" v-if="filteredPositiveNews.length">
      <h3 class="sg-header sg-bullish">📈 利好新闻 <small>{{ filteredPositiveNews.length }} 条</small></h3>
      <div v-for="n in filteredPositiveNews" :key="n._key" class="news-feed-card card-bullish" @click="$emit('show-stock-detail', n.code)">
        <div class="nfc-header">
          <span class="nfc-stock" @click.stop="$emit('show-stock-detail', n.code)">
            <strong>{{ n.code }}</strong>
            <span class="nfc-name">{{ n.name }}</span>
          </span>
          <el-tag size="small" type="danger" effect="dark" class="nfc-tag">利好</el-tag>
        </div>
        <div class="nfc-title">{{ n.title }}</div>
        <div class="nfc-meta">
          <span class="nfc-date">{{ n.date }}</span>
          <span class="nfc-source">{{ n.source }}</span>
          <span class="nfc-kws" v-if="n.keywords?.length">
            <el-tag v-for="kw in n.keywords.slice(0,4)" :key="kw" size="small" type="danger" effect="plain">{{ kw }}</el-tag>
          </span>
        </div>
      </div>
    </div>

    <!-- Negative News -->
    <div class="sentiment-group" v-if="filteredNegativeNews.length">
      <h3 class="sg-header sg-bearish">⚠️ 利空新闻 <small>{{ filteredNegativeNews.length }} 条</small></h3>
      <div v-for="n in filteredNegativeNews" :key="n._key" class="news-feed-card card-bearish" @click="$emit('show-stock-detail', n.code)">
        <div class="nfc-header">
          <span class="nfc-stock" @click.stop="$emit('show-stock-detail', n.code)">
            <strong>{{ n.code }}</strong>
            <span class="nfc-name">{{ n.name }}</span>
          </span>
          <el-tag size="small" type="success" effect="dark" class="nfc-tag">利空</el-tag>
        </div>
        <div class="nfc-title">{{ n.title }}</div>
        <div class="nfc-meta">
          <span class="nfc-date">{{ n.date }}</span>
          <span class="nfc-source">{{ n.source }}</span>
          <span class="nfc-kws" v-if="n.keywords?.length">
            <el-tag v-for="kw in n.keywords.slice(0,4)" :key="kw" size="small" type="success" effect="plain">{{ kw }}</el-tag>
          </span>
        </div>
      </div>
    </div>

    <el-empty v-if="filteredPositiveNews.length === 0 && filteredNegativeNews.length === 0" description="暂无舆情新闻数据" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  newsSearchText: string
  newsFeedPositive: any[]
  newsFeedNegative: any[]
  signalsWithNewsCount: number
}>()

const emit = defineEmits<{
  (e: 'update:newsSearchText', val: string): void
  (e: 'show-stock-detail', code: string): void
}>()

const localNewsSearchText = computed({
  get: () => props.newsSearchText,
  set: (val) => emit('update:newsSearchText', val)
})

const filteredPositiveNews = computed(() => {
  if (!props.newsSearchText) return props.newsFeedPositive
  const q = props.newsSearchText.toLowerCase()
  return props.newsFeedPositive.filter(n =>
    n.title.toLowerCase().includes(q) ||
    n.code.toLowerCase().includes(q) ||
    n.name.toLowerCase().includes(q)
  )
})

const filteredNegativeNews = computed(() => {
  if (!props.newsSearchText) return props.newsFeedNegative
  const q = props.newsSearchText.toLowerCase()
  return props.newsFeedNegative.filter(n =>
    n.title.toLowerCase().includes(q) ||
    n.code.toLowerCase().includes(q) ||
    n.name.toLowerCase().includes(q)
  )
})
</script>

<style scoped>
.sentiment-page { min-height: 60vh; }
.sentiment-group { margin-bottom: 24px; }
.sg-header {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 10px;
  padding: 6px 10px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.sg-header small { font-size: 12px; font-weight: 400; color: var(--text-muted); }
.sg-bullish { background: #fef0f0; color: var(--el-color-danger); }
.sg-bearish { background: #f0f9eb; color: var(--el-color-success); }

.news-feed-card {
  padding: 10px 12px;
  margin-bottom: 8px;
  background: var(--bg-card);
  border-left: 3px solid var(--el-color-danger);
  border-radius: 6px;
  cursor: pointer;
  transition: all .15s;
  box-shadow: 0 1px 2px rgba(0,0,0,.06);
}
.news-feed-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.1); transform: translateY(-1px); }
.news-feed-card.card-bearish { border-left-color: var(--el-color-success); }

.nfc-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.nfc-stock { cursor: pointer; font-size: 13px; }
.nfc-stock:hover { color: #409eff; }
.nfc-name { font-size: 12px; color: var(--text-muted); margin-left: 4px; }
.nfc-tag { margin-left: auto; font-size: 10px; height: 20px; line-height: 20px; }
.nfc-title { font-size: 13px; font-weight: 500; margin-bottom: 6px; line-height: 1.4; color: var(--text-primary); }
.nfc-meta { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-muted); flex-wrap: wrap; }
.nfc-date { white-space: nowrap; }
.nfc-source { white-space: nowrap; }
.nfc-kws { display: flex; gap: 2px; flex-wrap: wrap; }

.stats-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.stat-card { flex: 1; min-width: 100px; }
.stat-label { font-size: 12px; color: var(--text-muted, #999); }
.stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.stat-bullish .stat-value { color: var(--el-color-danger); }
.stat-bearish .stat-value { color: var(--el-color-success); }

.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.search-input { width: 200px; }
</style>
