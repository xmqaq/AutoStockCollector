<template>
  <div class="sm-sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title">
        <el-icon><Files /></el-icon>
        <span>策略资源管理器</span>
      </div>
      <div class="sidebar-actions">
        <el-button link size="small" @click="$emit('create')">
          <el-icon><Plus /></el-icon>
        </el-button>
        <el-button link size="small" @click="$emit('refresh')">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="sidebar-search">
      <el-input 
        v-model="searchText" 
        placeholder="搜索策略..." 
        size="small" 
        clearable 
        prefix-icon="Search" 
      />
    </div>

    <div class="sidebar-content" v-loading="loading">
      <el-collapse v-model="activeCollapse" class="strategy-collapse">
        
        <!-- 选股策略分组 -->
        <el-collapse-item name="selection">
          <template #title>
            <div class="group-title">
              <el-icon><Filter /></el-icon>
              <span>选股策略</span>
              <span class="count-badge">{{ selectionList.length }}</span>
            </div>
          </template>
          
          <div 
            v-for="item in selectionList" 
            :key="item._id"
            :class="['strategy-list-item', { 'is-active': activeId === item._id }]"
            @click="$emit('select', item)"
          >
            <div class="item-icon">
              <div :class="['status-dot', item.enabled ? 'is-active' : '']"></div>
            </div>
            <div class="item-content">
              <span class="item-name" :title="item.name">{{ item.name }}</span>
            </div>
            <div class="item-actions">
              <el-switch
                :model-value="item.enabled"
                size="small"
                @click.stop
                @change="(v: boolean) => $emit('toggle', item, v)"
              />
            </div>
          </div>
          <div v-if="selectionList.length === 0" class="empty-group">无匹配策略</div>
        </el-collapse-item>

        <!-- 交易策略分组 -->
        <el-collapse-item name="trading">
          <template #title>
            <div class="group-title">
              <el-icon><TrendCharts /></el-icon>
              <span>交易策略</span>
              <span class="count-badge">{{ tradingList.length }}</span>
            </div>
          </template>
          
          <div 
            v-for="item in tradingList" 
            :key="item._id"
            :class="['strategy-list-item', { 'is-active': activeId === item._id }]"
            @click="$emit('select', item)"
          >
            <div class="item-icon">
              <div :class="['status-dot', item.enabled ? 'is-active' : '']"></div>
            </div>
            <div class="item-content">
              <span class="item-name" :title="item.name">{{ item.name }}</span>
            </div>
            <div class="item-actions">
              <el-switch
                :model-value="item.enabled"
                size="small"
                @click.stop
                @change="(v: boolean) => $emit('toggle', item, v)"
              />
            </div>
          </div>
          <div v-if="tradingList.length === 0" class="empty-group">无匹配策略</div>
        </el-collapse-item>

      </el-collapse>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Files, Plus, Refresh, Search, Filter, TrendCharts } from '@element-plus/icons-vue'
import type { StrategyRule } from '@/types'

const props = defineProps<{
  list: StrategyRule[]
  activeId: string
  loading: boolean
}>()

defineEmits<{
  (e: 'select', item: StrategyRule): void
  (e: 'create'): void
  (e: 'refresh'): void
  (e: 'toggle', item: StrategyRule, val: boolean): void
}>()

const activeCollapse = ref(['selection', 'trading'])
const searchText = ref('')

const selectionList = computed(() => {
  return props.list.filter(item => 
    item.type === 'selection' && 
    item.name.toLowerCase().includes(searchText.value.toLowerCase())
  )
})

const tradingList = computed(() => {
  return props.list.filter(item => 
    item.type === 'trading' && 
    item.name.toLowerCase().includes(searchText.value.toLowerCase())
  )
})
</script>

<style scoped>
.sm-sidebar {
  width: 280px;
  height: 100%;
  background: var(--bg-soft);
  border-right: 1px solid var(--border-color-light);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden; /* 防止侧边栏整体被撑开 */
  transition: width 0.3s ease;
}

.sidebar-header {
  height: 60px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color-light);
  background: var(--bg-card);
}

.sidebar-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.sidebar-actions {
  display: flex;
  gap: 4px;
}

.sidebar-search {
  padding: 16px 20px 8px;
}

.sidebar-search :deep(.el-input__wrapper) {
  border-radius: 20px;
  box-shadow: 0 0 0 1px var(--border-color-light) inset;
  background: var(--bg-body);
}
.sidebar-search :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

/* 自定义滚动条 */
.sidebar-content::-webkit-scrollbar {
  width: 6px;
}
.sidebar-content::-webkit-scrollbar-thumb {
  background: var(--border-color-light);
  border-radius: 3px;
}
.sidebar-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

.strategy-collapse {
  border: none;
  --el-collapse-header-bg-color: transparent;
  --el-collapse-content-bg-color: transparent;
}

.strategy-collapse :deep(.el-collapse-item__header) {
  height: 44px;
  line-height: 44px;
  border-bottom: none;
  padding: 0 8px;
  font-size: 14px;
  transition: background-color 0.3s;
  border-radius: 6px;
}

.strategy-collapse :deep(.el-collapse-item__header:hover) {
  background-color: var(--bg-hover-subtle);
}

.strategy-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.strategy-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 12px;
}

.group-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: var(--text-primary);
  width: 100%;
}

.count-badge {
  background: var(--bg-elevated);
  color: var(--text-secondary);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  margin-left: auto;
  margin-right: 8px;
  font-family: var(--font-mono);
  border: 1px solid var(--border-color-light);
}

.strategy-list-item {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 12px 0 20px;
  margin-bottom: 6px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid transparent;
  position: relative;
}

.strategy-list-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background-color: var(--el-color-primary);
  border-radius: 0 4px 4px 0;
  transition: height 0.2s ease;
}

.strategy-list-item:hover {
  background: var(--bg-hover-subtle);
}

.strategy-list-item.is-active {
  background: var(--bg-card);
  border-color: var(--border-color-light);
  box-shadow: 0 2px 8px var(--bg-hover-subtle);
}

.strategy-list-item.is-active::before {
  height: 24px;
}

.item-icon {
  width: 18px;
  display: flex;
  align-items: center;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--text-faint);
  transition: all 0.3s ease;
}

.status-dot.is-active {
  background-color: var(--color-success);
  box-shadow: 0 0 8px var(--color-success);
}

.item-content {
  flex: 1;
  min-width: 0;
  margin-right: 12px;
}

.item-name {
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  color: var(--text-secondary);
  transition: color 0.3s;
}

.is-active .item-name {
  font-weight: 600;
  color: var(--el-color-primary);
}

.item-actions {
  display: flex;
  align-items: center;
  opacity: 0.8;
  transition: opacity 0.3s;
}

.strategy-list-item:hover .item-actions {
  opacity: 1;
}

.empty-group {
  padding: 12px 16px 12px 48px;
  font-size: 13px;
  color: var(--text-muted);
  font-style: italic;
}
</style>