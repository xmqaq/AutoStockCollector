<template>
  <div v-if="stats" class="stats-overview">
    <div class="stat-card total-card" :class="{ active: !activeType }" @click="$emit('filter', '')">
      <div class="stat-icon">
        <el-icon><DataLine /></el-icon>
      </div>
      <div class="stat-content">
        <span class="stat-label">今日资讯</span>
        <span class="stat-value">{{ stats.total }}</span>
      </div>
    </div>
    
    <div class="stat-card breaking-card">
      <div class="stat-icon">
        <el-icon><BellFilled /></el-icon>
      </div>
      <div class="stat-content">
        <span class="stat-label">突发新闻</span>
        <span class="stat-value highlight">{{ stats.breaking_count }}</span>
      </div>
    </div>

    <div class="stat-divider"></div>

    <div class="stat-tags-wrapper">
      <div class="stat-tags">
        <div 
          v-for="(count, type) in stats.by_type" 
          :key="type" 
          class="stat-tag-item"
          :class="{ active: activeType === String(type) }"
          @click="$emit('filter', String(type))"
        >
          <span class="type-name">{{ typeLabel(String(type)) }}</span>
          <span class="type-count">{{ count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { DataLine, BellFilled } from '@element-plus/icons-vue'
import type { NewsStats } from '@/api/news'

defineProps<{
  stats: NewsStats | null
  activeType?: string
}>()

defineEmits<{
  (e: 'filter', type: string): void
}>()

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
</script>

<style scoped>
.stats-overview {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--bg-card, #ffffff);
  border-radius: 12px;
  padding: 12px 20px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  position: relative;
}

/* 添加右侧渐变遮罩，提示用户可以向右滑动 */
.stat-tags-wrapper::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 32px;
  background: linear-gradient(to right, rgba(255,255,255,0) 0%, var(--bg-card, #ffffff) 100%);
  pointer-events: none;
}

.total-card, .breaking-card {
  flex-shrink: 0;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 8px;
  transition: all 0.3s;
  border: 1px solid transparent;
}

.stat-card:hover {
  background: var(--bg-soft, #f4f4f5);
}

.total-card.active {
  background: rgba(64, 158, 255, 0.05);
  border-color: rgba(64, 158, 255, 0.2);
}

.stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.total-card .stat-icon {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
}

.breaking-card .stat-icon {
  background: rgba(245, 108, 108, 0.1);
  color: #f56c6c;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted, #909399);
  margin-bottom: 2px;
}

.stat-value {
  font-size: 18px;
  font-weight: bold;
  color: var(--text-primary, #303133);
  line-height: 1;
}

.stat-value.highlight {
  color: #f56c6c;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background-color: var(--border-color-light, #ebeef5);
  margin: 0 4px;
  flex-shrink: 0;
}

.stat-tags-wrapper {
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  position: relative;
  /* 隐藏滚动条但保留滚动功能 (Webkit) */
  scrollbar-width: none; 
}

.stat-tags-wrapper::-webkit-scrollbar {
  display: none;
}

.stat-tags {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  width: max-content;
  padding: 2px 0;
}

.stat-tag-item {
  display: flex;
  align-items: center;
  background: var(--bg-soft, #f4f4f5);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid transparent;
  flex-shrink: 0;
}

.stat-tag-item:hover {
  background: var(--border-color-light, #ebeef5);
}

.stat-tag-item.active {
  background: rgba(64, 158, 255, 0.1);
  border-color: rgba(64, 158, 255, 0.2);
}

.type-name {
  color: var(--text-regular, #606266);
  margin-right: 8px;
}

.type-count {
  font-weight: 600;
  color: var(--el-color-primary, #409eff);
}
</style>
