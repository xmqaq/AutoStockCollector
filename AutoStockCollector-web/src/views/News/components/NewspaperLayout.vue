<template>
  <div class="newspaper-layout" v-loading="loading">
    <el-empty v-if="newsList.length === 0 && !loading" description="暂无资讯数据" />
    
    <div v-else class="newspaper-wrapper">
      <!-- 报纸头部风格标识（可选） -->
      <div class="newspaper-masthead">
        <div class="masthead-line"></div>
        <div class="masthead-date">{{ currentDate }}</div>
      </div>

      <div class="newspaper-content">
        <!-- 左侧主内容区（70%） -->
        <div class="main-column">
          <!-- 头条新闻 -->
          <div class="headline-section" v-if="headlineNews">
            <div class="article-meta">
              <span v-if="(headlineNews as any).is_breaking" class="breaking-badge">突发头条</span>
              <span class="meta-tag">{{ typeLabel((headlineNews as any).news_type) }}</span>
              <span class="meta-time">{{ formatTime(headlineNews.publish_date || headlineNews.datetime || headlineNews.date) }}</span>
            </div>
            
            <h1 class="headline-title" @click="openLink(headlineNews)">
              {{ headlineNews.title }}
            </h1>
            
            <p class="headline-summary" v-if="headlineNews.summary || headlineNews.content">
              <span class="drop-cap" v-if="headlineNews.summary || headlineNews.content">
                {{ (headlineNews.summary || headlineNews.content)!.charAt(0) }}
              </span>
              {{ (headlineNews.summary || headlineNews.content)!.substring(1) }}
            </p>
          </div>

          <!-- 次要新闻网格（两列排版） -->
          <div class="secondary-section" v-if="secondaryNews.length > 0">
            <div 
              class="secondary-article" 
              v-for="news in secondaryNews" 
              :key="news.title"
            >
              <h3 class="secondary-title" @click="openLink(news)">
                {{ news.title }}
              </h3>
              <p class="secondary-summary" v-if="news.summary || news.content">
                {{ truncate(news.summary || news.content || '', 80) }}
              </p>
              <div class="article-meta bottom-meta">
                <span class="meta-time">{{ formatTime(news.publish_date || news.datetime || news.date) }}</span>
                <span class="meta-source" v-if="news.source">{{ sourceLabel(news.source) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧边栏区（30%） -->
        <div class="side-column">
          <div class="sidebar-header">
            <h3>最新快讯</h3>
          </div>
          
          <div class="briefs-container" @mouseenter="isPaused = true" @mouseleave="isPaused = false">
            <div 
              class="briefs-scroll-wrap" 
              :style="{ 
                animationDuration: scrollDuration + 's', 
                animationPlayState: isPaused ? 'paused' : 'running' 
              }"
              v-if="sidebarNews.length > 0"
            >
              <!-- 第一份列表 -->
              <div class="briefs-list">
                <div 
                  class="brief-item" 
                  v-for="(news, index) in sidebarNews" 
                  :key="'orig-' + index"
                >
                  <div class="brief-time">
                    {{ formatTimeOnly(news.publish_date || news.datetime || news.date) }}
                  </div>
                  <div class="brief-content">
                    <h4 
                      class="brief-title" 
                      :class="{ 'is-breaking': (news as any).is_breaking }"
                      @click="openLink(news)"
                    >
                      {{ news.title }}
                    </h4>
                  </div>
                </div>
              </div>
              
              <!-- 复制一份列表用于无缝滚动拼接 -->
              <div class="briefs-list" aria-hidden="true" v-if="sidebarNews.length > 0">
                <div 
                  class="brief-item" 
                  v-for="(news, index) in sidebarNews" 
                  :key="'dup-' + index"
                >
                  <div class="brief-time">
                    {{ formatTimeOnly(news.publish_date || news.datetime || news.date) }}
                  </div>
                  <div class="brief-content">
                    <h4 
                      class="brief-title" 
                      :class="{ 'is-breaking': (news as any).is_breaking }"
                      @click="openLink(news)"
                    >
                      {{ news.title }}
                    </h4>
                  </div>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无快讯" :image-size="60" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import type { NewsRecord } from '@/types'

const props = defineProps<{
  newsList: NewsRecord[]
  loading: boolean
}>()

const currentDate = dayjs().format('YYYY年MM月DD日 dddd')
const isPaused = ref(false)

// 头条新闻：优先突发，否则取第一条
const headlineNews = computed(() => {
  if (!props.newsList.length) return null
  const breaking = props.newsList.find((n: any) => n.is_breaking)
  return breaking || props.newsList[0]
})

// 剩余新闻
const remainingNews = computed(() => {
  if (!headlineNews.value) return []
  return props.newsList.filter(n => n !== headlineNews.value)
})

// 次要深度新闻（带摘要），取前 8 条
const secondaryNews = computed(() => {
  return remainingNews.value.slice(0, 8)
})

// 侧边栏快讯，取剩下的
const sidebarNews = computed(() => {
  return remainingNews.value.slice(8)
})

// 根据快讯数量动态计算滚动时长，保证匀速滚动（每条约 3 秒）
const scrollDuration = computed(() => {
  return Math.max(sidebarNews.value.length * 3, 20)
})

// 工具方法
function formatTime(v: string | undefined | null) {
  if (!v) return ''
  return dayjs(v).format('YYYY-MM-DD HH:mm')
}

function formatTimeOnly(v: string | undefined | null) {
  if (!v) return ''
  return dayjs(v).format('HH:mm')
}

function truncate(str: string, len: number) {
  if (!str) return ''
  return str.length > len ? str.substring(0, len) + '...' : str
}

function openLink(news: any) {
  if (news.url) {
    window.open(news.url, '_blank')
  }
}

const NEWS_TYPE_MAP: Record<string, string> = {
  general:  '综合',
  futures:  '期货',
  nmetal:   '有色',
  research: '研报',
  stock:    '股票',
  forex:    '外汇',
  bond:     '债券',
  fund:     '基金',
}
function typeLabel(t: string): string {
  if (!t) return '资讯'
  return NEWS_TYPE_MAP[t] || NEWS_TYPE_MAP[t?.toLowerCase()] || t
}

const NEWS_SOURCE_MAP: Record<string, string> = {
  cls:    '财联社',
  sina:   '新浪财经',
  '新浪财经': '新浪财经',
  em:     '东方财富',
}
function sourceLabel(s: string): string {
  return NEWS_SOURCE_MAP[s] || s
}
</script>

<style scoped>
.newspaper-layout {
  flex: 1;
  background-color: #fdfbf7; /* 经典的报纸米黄色底 */
  color: #1a1a1a;
  min-height: 0;
  padding: 16px 24px;
  overflow: hidden; /* 防止最外层滚动，把滚动交给左侧容器 */
  display: flex;
  flex-direction: column;
}

.newspaper-wrapper {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
}

/* 报头修饰 */
.newspaper-masthead {
  margin-bottom: 12px;
  border-bottom: 2px solid #1a1a1a;
  padding-bottom: 4px;
  flex-shrink: 0;
}

.masthead-line {
  border-top: 1px solid #1a1a1a;
  height: 2px;
}

.masthead-date {
  font-family: "Times New Roman", "Songti SC", "SimSun", serif;
  font-size: 12px;
  text-align: right;
  margin-top: 2px;
  color: #4a4a4a;
}

/* 主体内容网格 */
.newspaper-content {
  display: flex;
  gap: 24px;
  flex: 1;
  min-height: 0;
}

.main-column {
  flex: 1;
  min-width: 0;
  overflow-y: auto; /* 让左侧内容独立滚动 */
  padding-right: 16px; /* 防止滚动条遮挡文字 */
}

/* Webkit 隐藏左侧滚动条但保留功能 */
.main-column::-webkit-scrollbar {
  width: 6px;
}
.main-column::-webkit-scrollbar-thumb {
  background-color: rgba(0,0,0,0.1);
  border-radius: 3px;
}

.side-column {
  width: 300px;
  flex-shrink: 0;
  border-left: 1px solid #d4d4d4;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
}

/* 字体设定 */
.headline-title, .secondary-title, .sidebar-header h3 {
  font-family: "Times New Roman", "Songti SC", "SimSun", serif;
}

/* 头条区域 */
.headline-section {
  margin-bottom: 20px;
}

.article-meta {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.breaking-badge {
  background: #cc0000;
  color: white;
  padding: 2px 4px;
  font-weight: bold;
}

.meta-tag {
  color: #005689;
  font-weight: 600;
}

.headline-title {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  margin: 0 0 10px 0;
  cursor: pointer;
  transition: color 0.2s;
}

.headline-title:hover {
  color: #005689;
}

.headline-summary {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  margin: 0;
  text-align: justify;
}

/* 首字母下沉 */
.drop-cap {
  float: left;
  font-size: 42px;
  line-height: 36px;
  padding-top: 2px;
  padding-right: 6px;
  font-family: "Times New Roman", "Songti SC", serif;
  font-weight: bold;
  color: #1a1a1a;
}

/* 次要新闻区 */
.secondary-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  border-top: 1px solid #1a1a1a;
  padding-top: 16px;
}

.secondary-article {
  display: flex;
  flex-direction: column;
}

.secondary-title {
  font-size: 16px;
  font-weight: bold;
  line-height: 1.3;
  margin: 0 0 6px 0;
  cursor: pointer;
}

.secondary-title:hover {
  color: #005689;
}

.secondary-summary {
  font-size: 13px;
  line-height: 1.5;
  color: #555;
  margin: 0 0 8px 0;
  flex: 1;
}

.bottom-meta {
  margin-bottom: 0;
  margin-top: auto;
}

/* 侧边栏快讯 */
.sidebar-header {
  border-top: 2px solid #1a1a1a;
  border-bottom: 1px solid #1a1a1a;
  margin-bottom: 12px;
  padding: 4px 0;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 15px;
  text-align: center;
  letter-spacing: 1px;
}

.briefs-container {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
  mask-image: linear-gradient(to bottom, transparent, black 2%, black 98%, transparent);
  -webkit-mask-image: linear-gradient(to bottom, transparent, black 2%, black 98%, transparent);
}

.briefs-scroll-wrap {
  display: flex;
  flex-direction: column;
  animation-name: scroll-up;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

.briefs-scroll-wrap:hover {
  animation-play-state: paused !important;
}

@keyframes scroll-up {
  0% { transform: translateY(0); }
  100% { transform: translateY(-50%); }
}

.briefs-list {
  display: flex;
  flex-direction: column;
}

.brief-item {
  display: flex;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #e0e0e0;
}

.brief-item:last-child {
  border-bottom: none;
}

.brief-time {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: #888;
  padding-top: 2px;
}

.brief-title {
  margin: 0;
  font-size: 13px;
  line-height: 1.4;
  font-weight: 500;
  cursor: pointer;
}

.brief-title:hover {
  color: #005689;
  text-decoration: underline;
}

.brief-title.is-breaking {
  color: #cc0000;
}

@media (max-width: 992px) {
  .newspaper-content {
    flex-direction: column;
  }
  .side-column {
    width: 100%;
    border-left: none;
    padding-left: 0;
    border-top: 2px solid #1a1a1a;
    padding-top: 24px;
  }
}
</style>