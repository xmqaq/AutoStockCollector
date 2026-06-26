<template>
  <div class="news-panel-card">
    <div class="panel-header">
      <div class="header-title">
        <el-icon class="title-icon"><component :is="icon" /></el-icon>
        {{ title }}
      </div>
      <div class="header-actions">
        <span class="total-badge">{{ totalCount }} 条</span>
        <el-button circle size="small" text @click="refresh" :loading="loading" title="刷新">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button circle size="small" text @click="$emit('expand', type)" title="放大查看">
          <el-icon><FullScreen /></el-icon>
        </el-button>
      </div>
    </div>
    
    <div class="panel-body" v-loading="loading && currentPage === 1">
      <el-empty v-if="newsList.length === 0 && !loading" description="暂无资讯" :image-size="60" />
      
      <div v-else class="compact-list" @scroll="handleScroll">
        <div 
          v-for="(news, idx) in newsList" 
          :key="idx" 
          class="compact-item"
          :class="{ 'is-breaking': (news as any).is_breaking }"
        >
          <div class="item-time">{{ formatTime(news.publish_date || news.datetime || news.date) }}</div>
          <div class="item-main">
            <div class="item-title" @click="toggleExpand(idx)">
              <span v-if="(news as any).is_breaking" class="breaking-badge">突发</span>
              {{ news.title }}
            </div>
            <div class="item-detail" v-if="expandedItems[idx]">
              <p>{{ news.summary || news.content || '暂无内容' }}</p>
              <el-link v-if="news.url" type="primary" :href="news.url" target="_blank" :underline="false">查看详情</el-link>
            </div>
          </div>
        </div>
        
        <div class="load-more-indicator" v-if="loading && currentPage > 1">
          <el-icon class="is-loading"><Loading /></el-icon> 加载中...
        </div>
        <div class="no-more" v-if="!loading && newsList.length >= totalCount && totalCount > 0">
          到底了
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { Refresh, Loading, FullScreen } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { newsApi } from '@/api/news'
import type { NewsRecord } from '@/types'

const props = defineProps<{
  title: string
  type: string
  keyword: string
  icon: any
}>()

defineEmits<{
  (e: 'expand', type: string): void
}>()

const loading = ref(false)
const newsList = ref<NewsRecord[]>([])
const totalCount = ref(0)
const currentPage = ref(1)
const pageSize = ref(15)
const expandedItems = ref<Record<number, boolean>>({})

function formatTime(v: string | undefined | null) {
  if (!v) return '--:--'
  const d = dayjs(v)
  if (!d.isValid()) return '--:--'
  return d.format('HH:mm')
}

function toggleExpand(idx: number) {
  expandedItems.value[idx] = !expandedItems.value[idx]
}

async function fetchNews(isAppend = false) {
  if (loading.value) return
  loading.value = true
  try {
    const params: Record<string, any> = {
      limit: pageSize.value,
      skip: (currentPage.value - 1) * pageSize.value,
      type: props.type
    }
    if (props.keyword) {
      params.code = props.keyword.trim()
    }
    
    const res = await newsApi.getNews(params)
    const data = res.data?.data || res.data || []
    const list = Array.isArray(data) ? data : []
    
    if (isAppend) {
      newsList.value = [...newsList.value, ...list]
    } else {
      newsList.value = list
    }
    totalCount.value = res.data?.total ?? (isAppend ? totalCount.value : list.length)
  } catch (e) {
    if (!isAppend) newsList.value = []
  } finally {
    loading.value = false
  }
}

function refresh() {
  currentPage.value = 1
  expandedItems.value = {}
  fetchNews(false)
}

function handleScroll(e: Event) {
  const target = e.target as HTMLElement
  if (target.scrollTop + target.clientHeight >= target.scrollHeight - 20) {
    if (!loading.value && newsList.value.length < totalCount.value) {
      currentPage.value++
      fetchNews(true)
    }
  }
}

watch(() => props.keyword, () => {
  refresh()
})

onMounted(() => {
  fetchNews()
})
</script>

<style scoped>
.news-panel-card {
  display: flex;
  flex-direction: column;
  background: var(--bg-card, #ffffff);
  border-radius: 8px;
  border: 1px solid var(--border-color-light, var(--border-color));
  height: 100%;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color-light, #ebeef5);
  background: var(--bg-soft, #f8f9fa);
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, var(--text-primary));
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-icon {
  color: var(--el-color-primary, #409eff);
  font-size: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.total-badge {
  font-size: 12px;
  color: var(--text-muted, var(--text-muted));
}

.panel-body {
  flex: 1;
  min-height: 0;
  position: relative;
}

.compact-list {
  height: 100%;
  overflow-y: auto;
  padding: 8px 12px;
  box-sizing: border-box;
}

.compact-item {
  display: flex;
  gap: 10px;
  padding: 10px 8px;
  border-bottom: 1px dashed var(--border-color-light, #ebeef5);
  transition: background-color 0.2s;
}

.compact-item:hover {
  background-color: var(--bg-soft, #f8f9fa);
  border-radius: 6px;
}

.compact-item:last-child {
  border-bottom: none;
}

.item-time {
  font-size: 13px;
  color: var(--text-muted, var(--text-muted));
  font-family: var(--font-mono, monospace);
  flex-shrink: 0;
  width: 42px;
  padding-top: 2px;
}

.item-main {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 14px;
  color: var(--text-primary, var(--text-primary));
  line-height: 1.5;
  cursor: pointer;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.item-title:hover {
  color: var(--el-color-primary, #409eff);
}

.breaking-badge {
  display: inline-block;
  background: var(--el-color-danger, var(--el-color-danger));
  color: #fff;
  font-size: 10px;
  padding: 0 4px;
  border-radius: 4px;
  margin-right: 6px;
  vertical-align: top;
  margin-top: 3px;
}

.is-breaking .item-title {
  font-weight: 500;
}

.item-detail {
  margin-top: 8px;
  padding: 8px 12px;
  background: var(--bg-soft, #f4f4f5);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-regular, var(--text-secondary));
  line-height: 1.6;
}

.item-detail p {
  margin: 0 0 6px 0;
}

.load-more-indicator, .no-more {
  text-align: center;
  padding: 12px 0;
  font-size: 12px;
  color: var(--text-muted, var(--text-muted));
}

.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>