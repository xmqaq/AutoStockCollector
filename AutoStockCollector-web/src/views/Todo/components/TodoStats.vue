<template>
  <el-row :gutter="20" class="stats-container">
    <el-col :span="8">
      <div class="stat-card total-card">
        <div class="stat-icon">
          <el-icon><List /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总计事项</div>
        </div>
      </div>
    </el-col>
    
    <el-col :span="8">
      <div class="stat-card done-card">
        <div class="stat-icon">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.done }}</div>
          <div class="stat-label">已完成</div>
        </div>
        <div class="stat-progress-wrapper">
          <el-progress 
            :percentage="donePercent" 
            :show-text="false" 
            :stroke-width="4" 
            color="var(--el-color-success)" 
          />
        </div>
      </div>
    </el-col>
    
    <el-col :span="8">
      <div class="stat-card pending-card">
        <div class="stat-icon">
          <el-icon><Clock /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.pending }}</div>
          <div class="stat-label">待完成</div>
        </div>
      </div>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { List, CircleCheck, Clock } from '@element-plus/icons-vue'

const props = defineProps<{
  stats: { total: number; done: number; pending: number }
}>()

const donePercent = computed(() =>
  props.stats.total
    ? Math.round((props.stats.done / props.stats.total) * 100)
    : 0
)
</script>

<style scoped>
.stats-container {
  margin-bottom: 20px;
}

.stat-card {
  position: relative;
  display: flex;
  align-items: center;
  padding: 24px;
  border-radius: 16px;
  background: var(--bg-card);
  box-shadow: 0 4px 16px var(--bg-hover-subtle);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  overflow: hidden;
  border: 1px solid #f0f2f5;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 16px;
  font-size: 28px;
  margin-right: 20px;
}

.total-card .stat-icon {
  background: #ecf5ff;
  color: #409eff;
}

.done-card .stat-icon {
  background: #f0f9eb;
  color: var(--el-color-success);
}

.pending-card .stat-icon {
  background: #fdf6ec;
  color: var(--el-color-warning);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
  font-family: "DIN Alternate", "SF Pro Display", sans-serif;
}

.stat-label {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 4px;
  font-weight: 500;
}

.stat-progress-wrapper {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
}

.stat-progress-wrapper :deep(.el-progress-bar__outer) {
  border-radius: 0;
  background-color: transparent;
}

.stat-progress-wrapper :deep(.el-progress-bar__inner) {
  border-radius: 0;
}
</style>
