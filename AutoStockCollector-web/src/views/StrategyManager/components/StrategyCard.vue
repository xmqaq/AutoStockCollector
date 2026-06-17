<template>
  <div :class="['modern-strategy-card', { 'is-disabled': !item.enabled }]">
    <!-- 装饰性背景光晕 -->
    <div class="card-glow"></div>
    
    <div class="card-content">
      <!-- 卡片头部 -->
      <div class="card-header">
        <div class="title-area">
          <div :class="['status-dot', item.enabled ? 'is-active' : '']"></div>
          <h3 class="name" :title="item.name">{{ item.name }}</h3>
        </div>
        <div class="actions-area">
          <el-tag 
            size="small" 
            :type="healthStatus.type" 
            effect="light" 
            class="health-badge"
          >
            {{ healthStatus.text }}
          </el-tag>
          <el-switch
            :model-value="item.enabled"
            size="small"
            :loading="togglingId === item._id"
            @click.stop
            @change="(v: boolean) => $emit('toggle', item, v)"
            style="margin-left: 12px;"
          />
        </div>
      </div>

      <!-- 描述信息 -->
      <div class="card-desc" :title="item.description">
        {{ item.description || '暂无描述' }}
      </div>

      <!-- 核心指标区 -->
      <div class="metrics-grid">
        <div class="metric-item">
          <span class="metric-label">启用指标</span>
          <span class="metric-value">
            <span class="highlight">{{ enabledCount(item) }}</span> / {{ totalCount(item) }}
          </span>
        </div>
        <div class="metric-item" v-if="item.type === 'selection'">
          <span class="metric-label">过滤规则</span>
          <span class="metric-value filter-text" :title="filterSummary(item)">
            {{ filterSummary(item) }}
          </span>
        </div>
      </div>

      <!-- 权重可视化条 -->
      <div class="weight-section">
        <div class="weight-header">
          <span class="label">维度占比分布</span>
        </div>
        <el-tooltip
          placement="top"
          effect="dark"
          :content="weightTooltip(item)"
        >
          <div class="weight-bar-container">
            <div
              v-for="(w, dim) in item.weights"
              :key="dim"
              class="weight-segment"
              :style="{ 
                width: (w * 100) + '%', 
                backgroundColor: dimColor(String(dim)),
                opacity: w > 0 ? 1 : 0 
              }"
            >
            </div>
          </div>
        </el-tooltip>
      </div>

      <!-- 底部操作栏 -->
      <div class="card-footer">
        <el-button-group class="action-btn-group">
          <el-button size="small" @click="$emit('edit', item)">
            <el-icon><Edit /></el-icon> 配置
          </el-button>
          <el-button size="small" @click="$emit('duplicate', item)" title="复制">
            <el-icon><CopyDocument /></el-icon>
          </el-button>
          <el-button 
            size="small" 
            type="danger" 
            plain
            @click="$emit('delete', item)" 
            title="删除"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </el-button-group>

        <el-button
          v-if="activeTab === 'selection'"
          type="primary"
          size="small"
          class="test-btn"
          :loading="testingId === item._id"
          @click="$emit('test', item)"
        >
          <el-icon><DataAnalysis /></el-icon> 运行回测
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Delete, Edit, CopyDocument, DataAnalysis } from '@element-plus/icons-vue'
import type { StrategyRule } from '@/types'
import { weightTooltip, dimColor, dimLabel, enabledCount, totalCount, filterSummary } from '../utils'

const props = defineProps<{
  item: StrategyRule
  activeTab: 'selection' | 'trading'
  togglingId: string
  testingId: string
}>()

defineEmits<{
  (e: 'delete', item: StrategyRule): void
  (e: 'toggle', item: StrategyRule, val: boolean): void
  (e: 'edit', item: StrategyRule): void
  (e: 'duplicate', item: StrategyRule): void
  (e: 'test', item: StrategyRule): void
}>()

// 计算策略的"健康度"
const healthStatus = computed(() => {
  const wTotal = Object.values(props.item.weights || {}).reduce((a, b) => a + b, 0)
  const eCount = enabledCount(props.item)
  
  if (Math.abs(wTotal - 1) > 0.01) {
    return { text: '权重异常', type: 'danger' as const }
  }
  if (eCount === 0) {
    return { text: '无因子', type: 'warning' as const }
  }
  if (eCount >= 3) {
    return { text: '极佳', type: 'success' as const }
  }
  return { text: '良好', type: 'primary' as const }
})
</script>

<style scoped>
.modern-strategy-card {
  position: relative;
  border-radius: 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  height: 100%;
}

.modern-strategy-card:hover {
  border-color: var(--el-color-primary-light-5);
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.06);
}

.modern-strategy-card.is-disabled {
  opacity: 0.6;
  filter: grayscale(0.5);
}

/* 顶部流光效果 */
.card-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--el-color-primary-light-3), var(--el-color-success-light-3));
  opacity: 0;
  transition: opacity 0.3s ease;
}

.modern-strategy-card:hover .card-glow {
  opacity: 1;
}

.card-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  flex: 1;
  position: relative;
  z-index: 1;
}

/* 头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.title-area {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--text-faint);
  flex-shrink: 0;
  transition: all 0.3s ease;
}

.status-dot.is-active {
  background-color: var(--el-color-success);
  box-shadow: 0 0 8px var(--el-color-success);
}

.name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.actions-area {
  display: flex;
  align-items: center;
}

.health-badge {
  font-weight: 600;
  border-radius: 6px;
}

/* 描述 */
.card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 16px;
  min-height: 39px; /* 保持两行高度 */
}

/* 指标网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  background: var(--bg-elevated);
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.metric-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.metric-value .highlight {
  color: var(--el-color-primary);
  font-size: 14px;
  font-weight: 600;
}

.filter-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 权重分布 */
.weight-section {
  margin-bottom: 20px;
  flex: 1;
}

.weight-header {
  margin-bottom: 8px;
}

.weight-header .label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.weight-bar-container {
  display: flex;
  height: 24px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--bg-soft);
}

.weight-segment {
  height: 100%;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.weight-segment:hover {
  filter: brightness(1.1);
}

/* 底部操作 */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px dashed var(--border-color);
  margin-top: auto;
}

.action-btn-group {
  display: flex;
}

.test-btn {
  border-radius: 8px;
  padding: 8px 16px;
  font-weight: 600;
}
</style>