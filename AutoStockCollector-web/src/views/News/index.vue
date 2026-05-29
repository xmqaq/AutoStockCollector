<template>
  <div class="news-view">
    <!-- Filter -->
    <el-card shadow="never" class="section-card">
      <div class="filter-bar">
        <el-input
          v-model="codeFilter"
          placeholder="股票代码（可选，留空查全部）"
          size="small"
          style="width:260px"
          clearable
        />
        <el-button type="primary" size="small" @click="loadNews">
          <el-icon><Search /></el-icon> 查询
        </el-button>
      </div>
    </el-card>

    <!-- News list -->
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header>
        <span>新闻舆情（共 {{ newsList.length }} 条）</span>
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
                  <span class="news-time">{{ fmtDateTime(news.publish_date || news.datetime || news.date) }}</span>
                  <el-tag v-if="news.source" size="small" type="info" class="news-source">
                    {{ news.source }}
                  </el-tag>
                </div>
              </div>
            </template>
            <div class="news-content">
              <p v-if="news.summary">{{ news.summary }}</p>
              <p v-else-if="news.content">{{ news.content }}</p>
              <p v-else class="text-muted">暂无摘要</p>
              <el-link v-if="news.url" type="primary" :href="news.url" target="_blank">
                阅读原文
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
import { fmtDateTime } from '@/utils/format'
import { normalizeCode } from '@/utils/stockCode'
import type { NewsRecord } from '@/types'
import { Search } from '@element-plus/icons-vue'

const loading = ref(false)
const newsList = ref<NewsRecord[]>([])
const codeFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const paginatedNews = computed(() =>
  newsList.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value)
)
watch(newsList, () => { currentPage.value = 1 })

async function loadNews() {
  loading.value = true
  try {
    const params: { code?: string; limit?: number } = { limit: 50 }
    if (codeFilter.value) {
      params.code = normalizeCode(codeFilter.value)
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

onMounted(() => {
  loadNews()
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
</style>
