<template>
  <div class="stats-bar">
    <el-card shadow="never" class="stat-card stat-total">
      <div class="stat-label">调用总数</div>
      <div class="stat-value">{{ stats.total ?? '-' }}</div>
    </el-card>
    <el-card shadow="never" class="stat-card stat-success">
      <div class="stat-label">成功</div>
      <div class="stat-value">{{ stats.success ?? '-' }}</div>
    </el-card>
    <el-card shadow="never" class="stat-card stat-fail">
      <div class="stat-label">失败</div>
      <div class="stat-value">{{ stats.fail ?? '-' }}</div>
    </el-card>
    <el-card shadow="never" class="stat-card">
      <div class="stat-label">今日调用</div>
      <div class="stat-value">{{ stats.today ?? '-' }}</div>
    </el-card>
    <el-card shadow="never" class="stat-card">
      <div class="stat-label">成功率</div>
      <div class="stat-value">{{ successRate }}%</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import type { AICallStats } from '@/api/aiCallHistory'

defineProps<{
  stats: AICallStats
  successRate: string | number
}>()
</script>

<style scoped>
.stats-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.stat-card { flex: 1; min-width: 100px; text-align: center; }
.stat-label { font-size: 12px; color: var(--text-muted); }
.stat-value { font-size: 22px; font-weight: 700; }
.stat-total .stat-value { color: var(--el-color-primary, #409eff); }
.stat-success .stat-value { color: var(--el-color-success, var(--el-color-success)); }
.stat-fail .stat-value { color: var(--el-color-danger, var(--el-color-danger)); }
</style>
