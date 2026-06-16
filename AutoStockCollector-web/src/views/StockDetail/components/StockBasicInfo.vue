<template>
  <el-card shadow="never" class="section-card overview-card" v-loading="infoLoading">
    <template #header>
      <div class="card-header">
        <div class="title-with-icon">
          <el-icon class="header-icon"><DataBoard /></el-icon>
          <span class="header-title">基础信息</span>
        </div>
        <div class="header-actions">
          <el-tag v-if="stockInfo?.name" type="primary" effect="dark" round size="large" class="stock-name-tag">
            {{ stockInfo.name }} <span class="stock-code-inline">{{ stockInfo.code }}</span>
          </el-tag>
          <el-button type="primary" plain round size="small" @click="handleGoToFinancial">
            <el-icon><Money /></el-icon> 查看财务数据
          </el-button>
        </div>
      </div>
    </template>
    
    <div v-if="stockInfo" class="info-layout">
      <!-- 核心指标突出显示 -->
      <div class="core-metrics">
        <div class="metric-box primary">
          <div class="metric-label">总市值</div>
          <div class="metric-value num">{{ fmtAmount(stockInfo.total_mv || 0) }}</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">市盈率PE(TTM)</div>
          <div class="metric-value num">{{ fmtNumber(stockInfo.pe) }}</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">市盈率PE(静)</div>
          <div class="metric-value num">{{ fmtNumber(stockInfo.pe_static) || '--' }}</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">市净率PB</div>
          <div class="metric-value num">{{ fmtNumber(stockInfo.pb) }}</div>
        </div>
      </div>

      <el-divider direction="vertical" class="layout-divider" />

      <!-- 其他基础信息 -->
      <div class="detail-grid">
        <div class="detail-item">
          <div class="detail-label"><el-icon><OfficeBuilding /></el-icon> 行业</div>
          <div class="detail-value">{{ stockInfo.industry || '--' }}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label"><el-icon><Location /></el-icon> 地区</div>
          <div class="detail-value">{{ stockInfo.area || '--' }}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label"><el-icon><Calendar /></el-icon> 上市日期</div>
          <div class="detail-value num">{{ stockInfo.list_date || '--' }}</div>
        </div>
      </div>
    </div>
    <el-empty v-else-if="!infoLoading" description="暂无基础信息" :image-size="60" />
  </el-card>
</template>

<script setup lang="ts">
import { DataBoard, OfficeBuilding, Location, Calendar, Money } from '@element-plus/icons-vue'
import { fmtAmount, fmtNumber } from '@/utils/format'
import type { StockInfo } from '@/types'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  infoLoading: boolean
  stockInfo: StockInfo | null
}>()

function handleGoToFinancial() {
  if (props.stockInfo?.code) {
    // 后期可替换为真实的路由跳转，例如：
    // router.push({ name: 'FinancialData', query: { code: props.stockInfo.code } })
    ElMessage.info(`即将跳转到 ${props.stockInfo.code} 的财务数据页面 (开发中)`)
  }
}
</script>

<style scoped>
.overview-card {
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
}

.overview-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 16px 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 18px;
  color: var(--el-color-primary);
}

.header-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stock-name-tag {
  font-size: 14px;
  padding: 0 16px;
  font-weight: bold;
}

.stock-code-inline {
  font-weight: normal;
  opacity: 0.8;
  margin-left: 6px;
  font-family: var(--font-mono);
}

.info-layout {
  display: flex;
  align-items: center;
  gap: 32px;
  padding: 8px;
}

.layout-divider {
  height: 80px;
  border-left-style: dashed;
}

/* 核心指标区域 */
.core-metrics {
  display: flex;
  gap: 24px;
  flex: 3;
}

.metric-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: 8px;
  background: var(--bg-soft);
  flex: 1;
  position: relative;
  overflow: hidden;
}

.metric-box::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: var(--border-heavy);
  border-radius: 4px 0 0 4px;
}

.metric-box.primary {
  background: var(--el-color-primary-light-9);
}

.metric-box.primary::before {
  background: var(--el-color-primary);
}

.metric-label {
  font-size: 13px;
  color: var(--text-muted);
}

.metric-value {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
}

.metric-box.primary .metric-value {
  color: var(--el-color-primary);
}

/* 详情网格区域 */
.detail-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-width: 200px;
}

.detail-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--border-color);
}

.detail-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.detail-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--text-muted);
}

.detail-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}
</style>