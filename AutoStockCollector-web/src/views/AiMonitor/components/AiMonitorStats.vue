<template>
  <div class="stats-bar">
    <el-card shadow="never" class="stat-card">
      <div class="stat-label">持仓监控</div>
      <div class="stat-value">{{ positionCount }}</div>
    </el-card>
    <el-card shadow="never" class="stat-card">
      <div class="stat-label">自选监控</div>
      <div class="stat-value">{{ watchlistCount }}</div>
    </el-card>
    <el-card shadow="never" class="stat-card">
      <div class="stat-label">短期买入</div>
      <div class="stat-value text-success">{{ shortBuyCount }}</div>
    </el-card>
    <el-card shadow="never" class="stat-card">
      <div class="stat-label">长期买入</div>
      <div class="stat-value text-success">{{ longBuyCount }}</div>
    </el-card>
    <el-card shadow="never" class="stat-card">
      <div class="stat-label">短期卖出</div>
      <div class="stat-value text-danger">{{ shortSellCount }}</div>
    </el-card>
    <el-card shadow="never" class="stat-card">
      <div class="stat-label">长期卖出</div>
      <div class="stat-value text-danger">{{ longSellCount }}</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  positionCount: number
  watchlistCount: number
  shortBuyCount: number
  longBuyCount: number
  shortSellCount: number
  longSellCount: number
}>()
</script>

<style scoped>
.stats-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-card { flex: 1; min-width: 100px; }
.stat-label { font-size: 12px; color: var(--text-muted, #999); }
.stat-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
</style>
