<template>
  <div class="news-view">
    <!-- Filter -->
    <el-card shadow="never" class="section-card">
      <div class="filter-bar">
        <el-select
          v-model="typeFilter"
          placeholder="新闻类型"
          size="small"
          style="width:140px"
          clearable
        >
          <el-option
            v-for="cat in categories"
            :key="cat.id"
            :label="cat.name"
            :value="cat.id"
          />
        </el-select>
        <el-input
          v-model="codeFilter"
          placeholder="关键词/股票名"
          size="small"
          style="width:160px"
          clearable
        />
        <el-button type="primary" size="small" @click="loadNews">
          <el-icon><Search /></el-icon> 查询
        </el-button>
      </div>
    </el-card>

    <!-- Stats -->
    <el-card v-if="stats" shadow="never" class="section-card stats-card">
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-label">总数</span>
          <span class="stat-value">{{ stats.total }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">突发</span>
          <span class="stat-value breaking">{{ stats.breaking_count }}</span>
        </div>
        <div v-for="(count, type) in stats.by_type" :key="type" class="stat-item">
          <span class="stat-label">{{ typeLabel(String(type)) }}</span>
          <span class="stat-value">{{ count }}</span>
        </div>
      </div>
    </el-card>

    <!-- News list -->
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header>
        <span>新闻舆情（共 {{ stats?.total ?? newsList.length }} 条）</span>
      </template>
      <el-empty v-if="newsList.length === 0 && !loading" description="暂无新闻数据" />
      <div v-else class="news-list">
        <el-collapse>
          <el-collapse-item
            v-for="(news, idx) in paginatedNews"
            :key="idx"
            :name="idx"
          >
            <template #title>
              <div class="news-item-title">
                <span class="news-headline">{{ news.title }}</span>
                <div class="news-meta">
                  <span class="news-time">{{ fmtNewsTime(news.publish_date || news.datetime || news.date) }}</span>
                  <el-tag v-if="(news as any).channel_name" size="small" type="info" class="news-source">
                    {{ (news as any).channel_name }}
                  </el-tag>
                  <el-tag v-else-if="(news as any).news_type" size="small" type="info" class="news-source">
                    {{ typeLabel((news as any).news_type) }}
                  </el-tag>
                  <el-tag v-if="news.source" size="small" type="info" class="news-source">
                    {{ sourceLabel(news.source) }}
                  </el-tag>
                  <el-tag v-if="(news as any).is_breaking" size="small" type="danger">突发</el-tag>
                </div>
              </div>
            </template>
            <div class="news-content">
              <p v-if="news.summary">{{ news.summary }}</p>
              <p v-else-if="news.content">{{ news.content }}</p>
              <p v-else-if="!news.url" class="text-muted">暂无内容</p>
              <el-link v-if="news.url" type="primary" :href="news.url" target="_blank">
                点击阅读原文
              </el-link>
            </div>
          </el-collapse-item>
        </el-collapse>
        <el-pagination
          v-if="newsList.length > pageSize"
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="newsList.length"
          layout="total, sizes, prev, pager, next"
          background
          class="table-pagination"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { newsApi } from '@/api/news'
import dayjs from 'dayjs'
import type { NewsRecord } from '@/types'
import type { NewsCategory, NewsStats } from '@/api/news'
import { Search } from '@element-plus/icons-vue'

/**
 * 智能时间格式：
 * - 精确到分钟 (HH:MM != 00:00)：显示 "YYYY-MM-DD HH:mm"
 * - 仅有日期 (时间为 00:00:00)：显示 "YYYY-MM-DD"
 * - null/空：显示 "--"
 */
function fmtNewsTime(v: string | undefined | null): string {
  if (!v) return '--'
  const d = dayjs(v)
  if (!d.isValid()) return '--'
  const timeStr = d.format('HH:mm')
  return timeStr === '00:00' ? d.format('YYYY-MM-DD') : d.format('YYYY-MM-DD HH:mm')
}

// 新闻类型中文映射
const NEWS_TYPE_MAP: Record<string, string> = {
  general:  '综合财经',
  futures:  '期货要闻',
  nmetal:   '有色金属',
  research: '机构研报',
  stock:    '股票',
  forex:    '外汇',
  bond:     '债券',
  fund:     '基金',
}
function typeLabel(t: string): string {
  return NEWS_TYPE_MAP[t] || NEWS_TYPE_MAP[t?.toLowerCase()] || t
}

// 来源中文映射（为多源接入预留）
const NEWS_SOURCE_MAP: Record<string, string> = {
  cls:    '财联社',
  sina:   '新浪财经',
  '新浪财经': '新浪财经',
  em:     '东方财富',
}
function sourceLabel(s: string): string {
  return NEWS_SOURCE_MAP[s] || s
}

const loading = ref(false)
const newsList = ref<NewsRecord[]>([])
const codeFilter = ref('')
const typeFilter = ref('')
const categories = ref<NewsCategory[]>([])
const stats = ref<NewsStats | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)

const paginatedNews = computed(() =>
  newsList.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value)
)
watch(newsList, () => { currentPage.value = 1 })

async function loadNews() {
  loading.value = true
  try {
    // 用 stats.total 作为动态 limit，保证拉取全量数据；无统计时兜底 2000
    const limit = stats.value?.total || 2000
    const params: Record<string, any> = { limit }
    if (codeFilter.value) {
      params.code = codeFilter.value.trim()   // 关键词搜索，后端做正则匹配
    }
    if (typeFilter.value) {
      params.type = typeFilter.value
    }
    const res = await newsApi.getNews(params)
    const data = res.data?.data || res.data || []
    newsList.value = Array.isArray(data) ? data : []
  } catch {
    newsList.value = []
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    const res = await newsApi.getCategories()
    categories.value = res.data?.data || []
  } catch {
    categories.value = []
  }
}

async function loadStats() {
  try {
    const res = await newsApi.getStats()
    stats.value = res.data?.data || null
  } catch {
    stats.value = null
  }
}

onMounted(async () => {
  await loadCategories()
  await loadStats()   // 先拿总数
  await loadNews()    // 再用总数作为 limit 全量拉取
})
</script>

<style scoped>
.news-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c;
  padding: 12px 16px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.news-list :deep(.el-collapse) {
  border: none;
}

.news-list :deep(.el-collapse) {
  border-top: 1px solid #2c2c2c;
}

.news-list :deep(.el-collapse-item) {
  border-left: 3px solid transparent;
  transition: border-color 0.2s;
  padding-left: 10px;
}

.news-list :deep(.el-collapse-item:hover) {
  border-left-color: #409eff;
}

.news-list :deep(.el-collapse-item.is-active) {
  border-left-color: #409eff;
}

.news-list :deep(.el-collapse-item__header) {
  background: transparent;
  border-bottom: 1px solid #2c2c2c;
  color: #e5eaf3;
  padding: 14px 0;
  height: auto;
  line-height: 1.4;
}

.news-list :deep(.el-collapse-item__wrap) {
  background: transparent;
  border-bottom: 1px solid #2c2c2c;
}

.news-list :deep(.el-collapse-item__content) {
  padding: 12px 0;
  color: #909399;
}

.news-item-title {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  padding-right: 16px;
}

.news-headline {
  font-size: 14px;
  color: #d5dae3;
  line-height: 1.5;
  font-weight: 500;
}

.news-meta {
  display: flex;
  gap: 10px;
  align-items: center;
}

.news-time {
  font-size: 12px;
  color: #7a8089;
}

.news-source {
  font-size: 11px;
}

.news-content {
  padding: 0 8px;
  font-size: 13px;
  color: #909399;
  line-height: 1.6;
}

.text-muted {
  color: #606266;
  font-style: italic;
}

.table-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.table-pagination :deep(.el-pagination__total),
.table-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  color: #909399;
}

.stats-card {
  background: #1a1a1a;
}

.stats-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
  padding: 8px 12px;
  background: #252525;
  border-radius: 6px;
}

.stat-label {
  font-size: 11px;
  color: #7a8089;
  text-transform: capitalize;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #409eff;
}

.stat-value.breaking {
  color: #f56c6c;
}
</style>
