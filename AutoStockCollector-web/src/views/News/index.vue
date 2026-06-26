<template>
  <div class="news-dashboard">
    <!-- 顶部数据概览 -->
    <div class="news-header-section">
      <NewsStats 
        :stats="stats" 
        :active-type="typeFilter"
        @filter="handleTypeFilter"
      />
    </div>

    <!-- 主体内容：左侧新闻流，右侧过滤器或全部作为新闻流顶部过滤器 -->
    <div class="news-main-section">
      <div class="news-feed-container">
        <div class="feed-header">
          <h2 class="feed-title">全球财经观察</h2>
          <NewsFilter 
            :categories="categories"
            v-model:typeFilter="typeFilter"
            v-model:codeFilter="codeFilter"
            @search="handleSearch"
          />
        </div>
        
        <NewspaperLayout 
          :loading="loading"
          :newsList="newsList"
        />

        <div class="pagination-wrapper" v-if="totalCount > 0">
          <el-pagination
            :current-page="currentPage"
            @update:current-page="currentPage = $event"
            :page-size="pageSize"
            @update:page-size="pageSize = $event"
            :page-sizes="[20, 50, 100]"
            :total="totalCount"
            layout="total, sizes, prev, pager, next, jumper"
            background
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { newsApi } from '@/api/news'
import type { NewsRecord } from '@/types'
import type { NewsCategory, NewsStats as NewsStatsType } from '@/api/news'

import NewsFilter from './components/NewsFilter.vue'
import NewsStats from './components/NewsStats.vue'
import NewspaperLayout from './components/NewspaperLayout.vue'

const loading = ref(false)
const newsList = ref<NewsRecord[]>([])
const codeFilter = ref('')
const typeFilter = ref('')
const categories = ref<NewsCategory[]>([])
const stats = ref<NewsStatsType | null>(null)
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

watch(currentPage, () => loadNews())
watch(pageSize, () => {
  if (currentPage.value !== 1) {
    currentPage.value = 1
  } else {
    loadNews()
  }
})

function handleSearch() {
  if (currentPage.value !== 1) {
    currentPage.value = 1
  } else {
    loadNews()
  }
}

function handleTypeFilter(type: string) {
  if (typeFilter.value === type) {
    typeFilter.value = ''
  } else {
    typeFilter.value = type
  }
  handleSearch()
}

async function loadNews() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      limit: pageSize.value,
      skip: (currentPage.value - 1) * pageSize.value,
    }
    if (codeFilter.value) {
      params.code = codeFilter.value.trim()
    }
    if (typeFilter.value) {
      params.type = typeFilter.value
    }
    const res = await newsApi.getNews(params)
    const data = res.data?.data || res.data || []
    newsList.value = Array.isArray(data) ? data : []
    totalCount.value = res.data?.total ?? newsList.value.length
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

onMounted(() => {
  Promise.all([loadCategories(), loadStats()])
  loadNews()
})
</script>

<style scoped>
.news-dashboard {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background-color: var(--bg-body, #f5f7fa);
  padding: 12px 16px;
  gap: 12px;
  box-sizing: border-box;
}

.news-header-section {
  flex-shrink: 0;
}

.news-main-section {
  flex: 1;
  display: flex;
  min-height: 0;
}

.news-feed-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-card, #ffffff);
  border-radius: 12px;
  box-shadow: 0 4px 16px var(--bg-hover-subtle);
  overflow: hidden;
  min-height: 0;
}

.dashboard-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 16px;
  padding: 16px;
  min-height: 0;
  background: var(--bg-body, #f5f7fa);
}

.feed-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color-light, #ebeef5);
  background: var(--bg-card, #ffffff);
}

.feed-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, var(--text-primary));
  position: relative;
  padding-left: 12px;
}

.feed-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 18px;
  background-color: var(--el-color-primary, #409eff);
  border-radius: 2px;
}

.pagination-wrapper {
  padding: 16px 24px;
  border-top: 1px solid var(--border-color-light, #ebeef5);
  display: flex;
  justify-content: flex-end;
  background: var(--bg-card, #ffffff);
}
</style>
