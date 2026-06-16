<template>
  <div class="fund-flow-view">
    <!-- Filter Bar -->
    <el-card shadow="never" class="section-card filter-card">
      <div class="filter-bar">
        <el-select v-model="topN" size="small" style="width:100px">
          <el-option label="Top 20" :value="20" />
          <el-option label="Top 50" :value="50" />
          <el-option label="Top 100" :value="100" />
        </el-select>
        <el-radio-group v-model="direction" size="small">
          <el-radio-button value="inflow">净流入</el-radio-button>
          <el-radio-button value="outflow">净流出</el-radio-button>
        </el-radio-group>
        <el-button type="primary" size="small" :loading="loading" @click="loadData">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        
        <div class="spacer"></div>

        <span v-if="dataDate" class="date-label">数据日期：{{ dataDate }}</span>
        
        <div class="view-switch">
          <el-radio-group v-model="currentView" size="small">
            <el-radio-button value="table">
              <el-icon><List /></el-icon> 列表
            </el-radio-button>
            <el-radio-button value="chart">
              <el-icon><DataBoard /></el-icon> 柱状图
            </el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </el-card>

    <!-- Content Area -->
    <div class="content-container">
      <!-- Ranking Table -->
      <FundFlowTable 
        v-if="currentView === 'table'"
        :loading="loading" 
        :rows="rows" 
        :direction="direction" 
        :topN="topN" 
      />

      <!-- Bar Chart -->
      <FundFlowChart 
        v-else-if="currentView === 'chart' && rows.length > 0" 
        :rows="rows" 
      />
      <el-empty v-else-if="currentView === 'chart' && rows.length === 0" description="暂无资金流向数据" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { fundFlowApi } from '@/api/fundFlow'
import { Refresh, List, DataBoard } from '@element-plus/icons-vue'

import FundFlowTable from './components/FundFlowTable.vue'
import FundFlowChart from './components/FundFlowChart.vue'

const loading = ref(false)
const rows = ref<Record<string, unknown>[]>([])
const dataDate = ref('')
const topN = ref(50)
const direction = ref<'inflow' | 'outflow'>('inflow')
const currentView = ref<'table' | 'chart'>('table')

async function loadData() {
  loading.value = true
  try {
    const limit = direction.value === 'outflow' ? topN.value : topN.value
    const res = await fundFlowApi.getRank({ limit })
    const data = res.data?.data || []
    dataDate.value = res.data?.date || ''
    // 净流出：按升序取前 N
    if (direction.value === 'outflow') {
      rows.value = [...data].sort((a: Record<string, unknown>, b: Record<string, unknown>) =>
        (a.main_net_inflow as number) - (b.main_net_inflow as number)
      ).slice(0, topN.value)
    } else {
      rows.value = data
    }
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch([topN, direction], loadData)

onMounted(loadData)
</script>

<style scoped>
.fund-flow-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow: hidden;
}

.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.filter-card {
  flex-shrink: 0;
}

.filter-card :deep(.el-card__body) {
  padding: 12px 16px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.spacer {
  flex: 1;
}

.date-label {
  font-size: 12px;
  color: var(--text-faint);
  margin-right: 12px;
}

.view-switch {
  display: flex;
  align-items: center;
  border-left: 1px solid var(--border-color);
  padding-left: 16px;
}

.content-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
