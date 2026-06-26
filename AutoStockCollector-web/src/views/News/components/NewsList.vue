<template>
  <div class="news-list-wrapper" v-loading="loading">
    <el-empty v-if="newsList.length === 0 && !loading" description="暂无新闻数据" />
    
    <div v-else class="news-feed">
      <div class="news-scroll-area">
        <div class="timeline-container">
          <div 
            v-for="(news, idx) in newsList" 
            :key="idx" 
            class="news-item"
            :class="{ 'is-breaking': (news as any).is_breaking }"
          >
            <!-- 时间线部分 -->
            <div class="timeline-axis">
              <div class="timeline-time">
                <div class="time-hhmm">{{ formatTimeOnly(news.publish_date || news.datetime || news.date) }}</div>
                <div class="time-mmdd">{{ formatDateOnly(news.publish_date || news.datetime || news.date) }}</div>
              </div>
              <div class="timeline-dot-wrapper">
                <div class="timeline-line" v-if="idx !== newsList.length - 1"></div>
                <div class="timeline-dot"></div>
                <div class="timeline-dot-ping" v-if="(news as any).is_breaking"></div>
              </div>
            </div>

            <!-- 内容卡片部分 -->
            <div class="news-content-card">
              <div class="news-header">
                <el-tag v-if="(news as any).is_breaking" size="small" type="danger" effect="dark" class="breaking-tag">突发</el-tag>
                <h3 class="news-title">{{ news.title }}</h3>
              </div>
              
              <div class="news-body">
                <p class="news-summary" :class="{ 'expanded': expandedItems[idx] }">
                  {{ news.summary || news.content || '暂无内容' }}
                </p>
                <span 
                  v-if="needsExpand(news.summary || news.content)" 
                  class="expand-btn" 
                  @click="toggleExpand(idx)"
                >
                  {{ expandedItems[idx] ? '收起' : '展开' }}
                </span>
              </div>
              
              <div class="news-footer">
                <div class="news-tags">
                  <el-tag v-if="(news as any).channel_name" size="small" type="info" class="meta-tag">
                    {{ (news as any).channel_name }}
                  </el-tag>
                  <el-tag v-else-if="(news as any).news_type" size="small" type="info" class="meta-tag clickable" @click="$emit('filter-type', (news as any).news_type)">
                    {{ typeLabel((news as any).news_type) }}
                  </el-tag>
                  <el-tag v-if="news.source" size="small" type="info" class="meta-tag">
                    {{ sourceLabel(news.source) }}
                  </el-tag>
                </div>
                
                <el-link v-if="news.url" type="primary" :href="news.url" target="_blank" :underline="false" class="read-more-link">
                  阅读原文 <el-icon class="el-icon--right"><ArrowRight /></el-icon>
                </el-link>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="pagination-wrapper" v-if="totalCount > 0">
        <el-pagination
          :current-page="currentPage"
          @update:current-page="$emit('update:currentPage', $event)"
          :page-size="pageSize"
          @update:page-size="$emit('update:pageSize', $event)"
          :page-sizes="[20, 50, 100]"
          :total="totalCount"
          layout="total, sizes, prev, pager, next, jumper"
          background
          class="table-pagination"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import type { NewsRecord } from '@/types'

defineProps<{
  loading: boolean
  newsList: NewsRecord[]
  totalCount: number
  currentPage: number
  pageSize: number
}>()

defineEmits<{
  (e: 'update:currentPage', val: number): void
  (e: 'update:pageSize', val: number): void
  (e: 'filter-type', val: string): void
}>()

const expandedItems = ref<Record<number, boolean>>({})

function toggleExpand(idx: number) {
  expandedItems.value[idx] = !expandedItems.value[idx]
}

function needsExpand(text?: string): boolean {
  return text ? text.length > 150 : false
}

function formatTimeOnly(v: string | undefined | null): string {
  if (!v) return '--:--'
  const d = dayjs(v)
  if (!d.isValid()) return '--:--'
  return d.format('HH:mm')
}

function formatDateOnly(v: string | undefined | null): string {
  if (!v) return '--/--'
  const d = dayjs(v)
  if (!d.isValid()) return '--/--'
  return d.format('MM-DD')
}

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
.news-list-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--bg-card, #ffffff);
}

.news-feed {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.news-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.timeline-container {
  display: flex;
  flex-direction: column;
}

.news-item {
  display: flex;
  position: relative;
  margin-bottom: 24px;
}

.news-item:last-child {
  margin-bottom: 0;
}

.timeline-axis {
  display: flex;
  width: 90px;
  flex-shrink: 0;
  position: relative;
}

.timeline-time {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  width: 60px;
  padding-top: 4px;
  padding-right: 16px;
}

.time-hhmm {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, var(--text-primary));
  font-family: var(--font-mono, monospace);
  line-height: 1.2;
}

.time-mmdd {
  font-size: 12px;
  color: var(--text-muted, var(--text-muted));
  margin-top: 2px;
}

.timeline-dot-wrapper {
  position: relative;
  width: 14px;
  display: flex;
  justify-content: center;
}

.timeline-line {
  position: absolute;
  top: 20px;
  bottom: -44px; /* Extends to next item */
  left: 50%;
  transform: translateX(-50%);
  width: 2px;
  background-color: var(--border-color-light, #ebeef5);
}

.timeline-dot {
  position: absolute;
  top: 8px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--border-color, #dcdfe6);
  border: 2px solid var(--bg-card, #ffffff);
  box-sizing: content-box;
  z-index: 1;
  transition: all 0.3s;
}

.news-item:hover .timeline-dot {
  background-color: var(--el-color-primary, #409eff);
  transform: scale(1.2);
}

/* 突发新闻特效 */
.news-item.is-breaking .timeline-dot {
  background-color: var(--el-color-danger, var(--el-color-danger));
}

.timeline-dot-ping {
  position: absolute;
  top: 8px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--el-color-danger, var(--el-color-danger));
  opacity: 0.6;
  animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
  z-index: 0;
}

@keyframes ping {
  75%, 100% {
    transform: scale(2.5);
    opacity: 0;
  }
}

.news-content-card {
  flex: 1;
  background: var(--bg-soft, #f8f9fa);
  border-radius: 8px;
  padding: 16px 20px;
  margin-left: 16px;
  transition: all 0.3s;
  border: 1px solid transparent;
}

.news-item:hover .news-content-card {
  background: var(--bg-card, #ffffff);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-color: var(--border-color-light, var(--border-color));
}

.news-item.is-breaking .news-content-card {
  background: rgba(245, 108, 108, 0.04);
}

.news-item.is-breaking:hover .news-content-card {
  background: var(--bg-card, #ffffff);
  border-color: rgba(245, 108, 108, 0.2);
}

.news-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.breaking-tag {
  margin-top: 2px;
  flex-shrink: 0;
}

.news-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, var(--text-primary));
  line-height: 1.5;
}

.news-body {
  margin-bottom: 12px;
  position: relative;
}

.news-summary {
  margin: 0;
  font-size: 14px;
  color: var(--text-regular, var(--text-secondary));
  line-height: 1.6;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
  transition: all 0.3s;
}

.news-summary.expanded {
  display: block;
  -webkit-line-clamp: unset;
}

.expand-btn {
  font-size: 13px;
  color: var(--el-color-primary, #409eff);
  cursor: pointer;
  margin-top: 4px;
  display: inline-block;
}

.expand-btn:hover {
  opacity: 0.8;
}

.news-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-color-light, #ebeef5);
}

.news-tags {
  display: flex;
  gap: 8px;
}

.meta-tag {
  border: none;
  background: rgba(144, 147, 153, 0.1);
  color: var(--text-muted, var(--text-muted));
}

.meta-tag.clickable {
  cursor: pointer;
  transition: all 0.2s;
}

.meta-tag.clickable:hover {
  color: var(--el-color-primary, #409eff);
  background: rgba(64, 158, 255, 0.1);
}

.read-more-link {
  font-size: 13px;
}

.pagination-wrapper {
  padding: 16px 24px;
  border-top: 1px solid var(--border-color-light, #ebeef5);
  display: flex;
  justify-content: flex-end;
  background: var(--bg-card, #ffffff);
}
</style>
