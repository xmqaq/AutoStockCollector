<template>
  <el-row v-if="!dataLoaded" :gutter="16" class="metric-cards">
    <el-col v-for="i in 4" :key="i" :span="6">
      <div class="metric-card sk-card">
        <div class="sk-line sk-label-line"></div>
        <div class="sk-line sk-value-line"></div>
      </div>
    </el-col>
  </el-row>
  <el-row v-else :gutter="16" class="metric-cards">
    <!-- Card 1: Backend Status (Primary Gradient) -->
    <el-col :span="6">
      <div class="metric-card metric-card--primary">
        <div class="metric-content">
          <div class="metric-label">后端状态</div>
          <div class="metric-value-wrapper">
            <div :class="['status-dot-large', collectStore.backendOnline ? 'online' : 'offline']"></div>
            <div class="metric-value">{{ collectStore.backendOnline ? '正常运行' : '离线' }}</div>
          </div>
        </div>
        <el-icon class="metric-icon-bg"><Monitor /></el-icon>
      </div>
    </el-col>
    <!-- Card 2: Collection Progress -->
    <el-col :span="6">
      <div class="metric-card">
        <div class="metric-content">
          <div class="metric-label">采集完成度</div>
          <div class="metric-value-wrapper">
            <div class="metric-value num">{{ collectStore.completedCount }}</div>
            <div class="metric-sub">/ 8 类</div>
          </div>
        </div>
        <el-icon class="metric-icon-bg"><DataAnalysis /></el-icon>
      </div>
    </el-col>
    <!-- Card 3: Total Records -->
    <el-col :span="6">
      <div class="metric-card">
        <div class="metric-content">
          <div class="metric-label">累计成功条数</div>
          <div class="metric-value-wrapper">
            <div class="metric-value num text-gradient">{{ fmtAmount(collectStore.totalSuccessCount) }}</div>
          </div>
        </div>
        <el-icon class="metric-icon-bg"><TrendCharts /></el-icon>
      </div>
    </el-col>
    <!-- Card 4: News -->
    <el-col :span="6">
      <div class="metric-card">
        <div class="metric-content">
          <div class="metric-label">最新新闻条数</div>
          <div class="metric-value-wrapper">
            <div class="metric-value num">{{ newsCount }}</div>
            <div class="metric-sub"></div>
          </div>
        </div>
        <el-icon class="metric-icon-bg"><ChatDotRound /></el-icon>
      </div>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { useCollectStore } from '@/stores/collectStore'
import { fmtAmount } from '@/utils/format'
import { Monitor, DataAnalysis, TrendCharts, ChatDotRound } from '@element-plus/icons-vue'

defineProps<{
  dataLoaded: boolean
  newsCount: number
}>()

const collectStore = useCollectStore()
</script>

<style scoped>
/* --- Metric Cards --- */
.metric-cards {
  margin-bottom: 8px;
}

.metric-card {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--brand-300);
}

.metric-card--primary {
  background: linear-gradient(135deg, var(--brand-600) 0%, var(--brand-800) 100%);
  border: none;
  box-shadow: 0 8px 24px -6px rgba(79, 70, 229, 0.5);
}

.metric-card--primary .metric-label,
.metric-card--primary .metric-value,
.metric-card--primary .metric-icon-bg {
  color: #fff;
}

.metric-card--primary:hover {
  box-shadow: 0 12px 28px -6px rgba(79, 70, 229, 0.6);
  border-color: transparent;
}

.metric-content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
}

.metric-value-wrapper {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.metric-value {
  font-size: 32px;
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1;
  letter-spacing: -0.02em;
}

.metric-sub {
  font-size: 14px;
  color: var(--text-muted);
  font-weight: 500;
}

.text-gradient {
  background: linear-gradient(135deg, var(--brand-500) 0%, #3b82f6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.metric-icon-bg {
  position: absolute;
  right: -10px;
  bottom: -20px;
  font-size: 100px;
  opacity: 0.04;
  color: var(--brand-600);
  transform: rotate(-15deg);
  transition: transform 0.4s ease;
}

.metric-card:hover .metric-icon-bg {
  transform: rotate(0deg) scale(1.1);
}

.metric-card--primary .metric-icon-bg {
  opacity: 0.15;
  color: #fff;
}

/* Status Dot */
.status-dot-large {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  position: relative;
}

.status-dot-large.online {
  background-color: #10b981;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.6);
}

.status-dot-large.offline {
  background-color: #ef4444;
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.6);
}

/* --- Skeleton --- */
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.sk-line {
  background: linear-gradient(
    90deg,
    var(--bg-hover-subtle) 25%,
    var(--bg-hover) 50%,
    var(--bg-hover-subtle) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 4px;
}

.sk-card {
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
}

.sk-label-line { height: 16px; width: 40%; }
.sk-value-line { height: 32px; width: 70%; }
</style>
