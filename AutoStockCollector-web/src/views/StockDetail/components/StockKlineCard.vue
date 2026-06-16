<template>
  <el-card shadow="never" class="section-card kline-card" v-loading="klineLoading">
    <template #header>
      <div class="card-header">
        <span class="header-title">K线图与智能标注</span>
        <div class="date-filter">
          <el-date-picker
            :model-value="klineDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY年MM月DD日"
            value-format="YYYY-MM-DD"
            size="small"
            style="width:300px"
            :shortcuts="dateShortcuts"
            :clearable="false"
            @update:model-value="$emit('update:klineDateRange', $event)"
            @change="$emit('change-date')"
          />
        </div>
      </div>
    </template>
    <div class="kline-container">
      <KlineChart 
        v-if="klineData.length > 0" 
        :data="klineData" 
        :annotations="aiAnnotations"
        :support-levels="aiSupportLevels"
        :resistance-levels="aiResistanceLevels"
        chart-height="500px" 
      />
      <el-empty v-else-if="!klineLoading" :description="emptyKlineHint" :image-size="80" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import KlineChart from '@/components/KlineChart/index.vue'
import type { KlineRecord, AIAnnotation, PriceLevel } from '@/types'

defineProps<{
  klineLoading: boolean
  klineDateRange: [string, string]
  klineData: KlineRecord[]
  aiAnnotations: AIAnnotation[]
  aiSupportLevels: PriceLevel[]
  aiResistanceLevels: PriceLevel[]
  emptyKlineHint: string
  dateShortcuts: any[]
}>()

defineEmits<{
  (e: 'update:klineDateRange', value: [string, string]): void
  (e: 'change-date'): void
}>()
</script>

<style scoped>
.kline-card {
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
}

.kline-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 16px 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
}

.date-filter {
  display: flex;
  align-items: center;
}

.kline-container {
  padding: 8px 0;
}
</style>