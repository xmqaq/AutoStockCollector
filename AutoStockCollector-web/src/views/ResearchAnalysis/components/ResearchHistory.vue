<template>
  <el-card shadow="never" class="ra-history">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <span class="header-icon">📜</span>
          <span class="header-title">历史分析记录</span>
        </div>
        <span class="header-subtitle">点击记录行可快速查看之前的分析报告</span>
      </div>
    </template>
    <div v-if="history.length === 0" class="empty-state">
      <el-empty description="暂无分析记录，请选择上方行业板块开始智能分析" :image-size="120" />
    </div>
    <el-table
      v-else
      :data="history"
      stripe
      size="default"
      highlight-current-row
      @row-click="$emit('view-history', $event)"
      class="history-table"
      :header-cell-style="{ background: 'var(--el-fill-color-light)', color: 'var(--el-text-color-primary)', fontWeight: 600 }"
    >
      <el-table-column prop="created_at" label="分析时间" width="180">
        <template #default="{ row }">
          <div class="time-cell">
            <el-icon><Clock /></el-icon>
            {{ row.created_at }}
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="sectors" label="分析板块" min-width="250">
        <template #default="{ row }">
          <div class="sector-tags">
            <el-tag 
              v-for="s in row.sectors" 
              :key="s" 
              size="small" 
              effect="plain"
              class="sector-tag"
            >
              {{ s }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="result.candidate_count" label="提取候选标的" width="120" align="center">
        <template #default="{ row }">
          <el-tag type="success" effect="light" round v-if="row.result?.candidate_count">
            {{ row.result.candidate_count }} 只
          </el-tag>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="result.elapsed_seconds" label="引擎耗时" width="100" align="center">
        <template #default="{ row }">
          <span class="time-text">{{ row.result?.elapsed_seconds?.toFixed(1) || '-' }}s</span>
        </template>
      </el-table-column>
      <el-table-column prop="result.sector_details" label="研报数据来源" min-width="200">
        <template #default="{ row }">
          <div class="source-list">
            <el-tooltip 
              v-for="(det, sec) in row.result?.sector_details || {}" 
              :key="sec"
              :content="`${sec}: 从 ${det.source} 提取了 ${det.report_count} 份研报`"
              placement="top"
            >
              <span class="source-item">
                <span class="source-name">{{ det.source }}</span>
                <span class="source-count">{{ det.report_count }}</span>
              </span>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="{ row }">
          <el-button 
            v-if="row.task_id" 
            size="small" 
            type="primary" 
            link 
            :icon="Download" 
            @click.stop="$emit('export-history', row.task_id, row.sectors)"
          >
            导出
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { Download, Clock } from '@element-plus/icons-vue'
import type { HistoryItem } from '@/api/researchAnalysis'

defineProps<{
  history: HistoryItem[]
}>()

defineEmits<{
  (e: 'view-history', row: HistoryItem): void
  (e: 'export-history', taskId: string, sectors: string[]): void
}>()
</script>

<style scoped>
.ra-history {
  border-radius: 16px;
  border: none;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}
.ra-history :deep(.el-card__header) {
  padding: 16px 24px;
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-icon {
  font-size: 20px;
}
.header-title {
  font-weight: 600;
  font-size: 16px;
  color: var(--el-text-color-primary);
}
.header-subtitle {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.empty-state { 
  padding: 60px 0; 
}

.history-table { 
  cursor: pointer; 
  --el-table-row-hover-bg-color: var(--el-color-primary-light-9);
}
.history-table :deep(td.el-table__cell) {
  padding: 12px 0;
}

.time-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-text-color-regular);
  font-family: var(--el-font-family);
}

.sector-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.sector-tag {
  border-radius: 4px;
}

.text-muted {
  color: var(--el-text-color-placeholder);
}

.time-text {
  font-family: Monaco, Consolas, monospace;
  color: var(--el-text-color-secondary);
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.source-item {
  display: inline-flex;
  align-items: center;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 12px;
}
.source-name {
  color: var(--el-text-color-regular);
  margin-right: 4px;
}
.source-count {
  color: var(--el-color-primary);
  font-weight: 600;
  background: #fff;
  padding: 0 4px;
  border-radius: 2px;
}
</style>
