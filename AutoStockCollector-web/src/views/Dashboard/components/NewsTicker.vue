<template>
  <div class="news-ticker-container">
    <div class="news-ticker-bar" @click="isNewsExpanded = !isNewsExpanded">
      <div class="ticker-label">
        <el-icon><ChatDotRound /></el-icon>
        <span>最新资讯</span>
      </div>
      
      <div class="ticker-content" v-if="newsList.length > 0">
        <div class="ticker-item" :key="currentNewsIndex">
          <span class="ticker-time">{{ fmtDateTime(newsList[currentNewsIndex].publish_date || newsList[currentNewsIndex].datetime || newsList[currentNewsIndex].date).split(' ')[1] }}</span>
          <span class="ticker-title">{{ newsList[currentNewsIndex].title }}</span>
        </div>
      </div>
      <div class="ticker-content empty" v-else>
        <span>暂无新闻</span>
      </div>

      <div class="ticker-action">
        <el-icon class="expand-icon" :class="{ 'is-expanded': isNewsExpanded }"><ArrowDown /></el-icon>
      </div>
    </div>

    <!-- Collapsible News List -->
    <div class="news-collapse-panel" :class="{ 'is-expanded': isNewsExpanded }">
      <div class="news-list-inner">
        <div v-if="newsList.length === 0" class="empty-state">
          <el-empty description="暂无新闻" :image-size="60" />
        </div>
        <div v-else class="news-grid">
          <div
            v-for="(news, idx) in newsList"
            :key="idx"
            class="news-card"
            @click.stop="goToNews(news)"
          >
            <div class="news-time-col">
              <div class="time">{{ fmtDateTime(news.publish_date || news.datetime || news.date).split(' ')[1] }}</div>
              <div class="date">{{ fmtDateTime(news.publish_date || news.datetime || news.date).split(' ')[0].slice(5) }}</div>
            </div>
            <div class="news-content-col">
              <div class="news-title">{{ news.title }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ChatDotRound, ArrowDown } from '@element-plus/icons-vue'
import { fmtDateTime } from '@/utils/format'
import type { NewsRecord } from '@/types'

const props = defineProps<{
  newsList: NewsRecord[]
}>()

const router = useRouter()
const isNewsExpanded = ref(false)
const currentNewsIndex = ref(0)
let tickerTimer: ReturnType<typeof setInterval> | null = null

function startTicker() {
  stopTicker()
  tickerTimer = setInterval(() => {
    if (props.newsList.length > 0 && !isNewsExpanded.value) {
      currentNewsIndex.value = (currentNewsIndex.value + 1) % props.newsList.length
    }
  }, 4000)
}

function stopTicker() {
  if (tickerTimer) {
    clearInterval(tickerTimer)
    tickerTimer = null
  }
}

watch(() => props.newsList, (newVal) => {
  if (newVal.length > 0) {
    startTicker()
  }
}, { immediate: true })

onUnmounted(() => {
  stopTicker()
})

function goToNews(news: NewsRecord) {
  if (news.url) {
    window.open(news.url, '_blank', 'noopener,noreferrer')
  } else {
    router.push('/news')
  }
}
</script>

<style scoped>
.news-ticker-container {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  margin-bottom: 0;
}

.news-ticker-bar {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  cursor: pointer;
  transition: background-color 0.2s;
  background: var(--bg-elevated);
}

.news-ticker-bar:hover {
  background: var(--bg-hover-subtle);
}

.ticker-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--brand-500);
  font-weight: 600;
  font-size: 14px;
  padding-right: 16px;
  border-right: 1px solid var(--border-color);
  margin-right: 16px;
  white-space: nowrap;
}

.ticker-content {
  flex: 1;
  overflow: hidden;
  position: relative;
  height: 24px;
  display: flex;
  align-items: center;
}

.ticker-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  animation: slideUp 0.4s ease-out;
}

.ticker-time {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 13px;
  white-space: nowrap;
}

.ticker-title {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ticker-title:hover {
  color: var(--brand-500);
}

.ticker-content.empty {
  color: var(--text-muted);
  font-size: 14px;
}

.ticker-action {
  padding-left: 16px;
  color: var(--text-muted);
}

.expand-icon {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.expand-icon.is-expanded {
  transform: rotate(180deg);
}

.news-collapse-panel {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  background: var(--bg-card);
}

.news-collapse-panel.is-expanded {
  max-height: 500px;
  border-top: 1px solid var(--border-color);
}

.news-list-inner {
  padding: 16px 20px;
  overflow-y: auto;
  max-height: 500px;
}

.news-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px 24px;
}

.news-card {
  display: flex;
  gap: 16px;
  padding: 16px;
  border-radius: var(--radius-md);
  background: var(--bg-soft);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.news-card:hover {
  background: var(--bg-hover-subtle);
  border-color: var(--border-color);
  transform: translateX(4px);
}

.news-card .news-time-col {
  flex-shrink: 0;
  text-align: right;
  border-right: 2px solid var(--brand-300);
  padding-right: 12px;
  min-width: 60px;
}

.news-card .news-time-col .time {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.news-card .news-time-col .date {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.news-card .news-content-col {
  flex: 1;
}

.news-card .news-content-col .news-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.news-card:hover .news-title {
  color: var(--brand-500);
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
