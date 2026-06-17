<template>
  <div class="dragon-tiger">
    <!-- 现代仪表盘：数据概览 -->
    <el-row :gutter="16" class="overview-panel">
      <el-col :span="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-title">当前页上榜总额</div>
          <div class="stat-value">{{ fmtAmount(summary.totalAmount) }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-title">最大净买入</div>
          <div class="stat-value danger">
            {{ summary.topBuy.name || '--' }}
            <span class="sub-value" v-if="summary.topBuy.name">{{ fmtAmount(summary.topBuy.amount) }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" class="stat-card">
          <div class="stat-title">最大净卖出</div>
          <div class="stat-value success">
            {{ summary.topSell.name || '--' }}
            <span class="sub-value" v-if="summary.topSell.name">{{ fmtAmount(summary.topSell.amount) }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <DragonTigerFilter @search="onSearch" />
    <DragonTigerTable
      :data="tableData"
      :loading="loading"
      :total="total"
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      @page-change="onPageChange"
      @size-change="onPageSizeChange"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { dragonTigerApi } from '@/api/dragonTiger'
import { normalizeCode } from '@/utils/stockCode'
import { fmtAmount } from '@/utils/format'
import type { DragonTigerRecord } from '@/types'
import DragonTigerFilter from './components/DragonTigerFilter.vue'
import DragonTigerTable from './components/DragonTigerTable.vue'

const loading = ref(false)
const tableData = ref<DragonTigerRecord[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)

const currentFilter = ref<{ dateRange: [string, string] | null, code: string }>({
  dateRange: null,
  code: ''
})

const summary = computed(() => {
  let totalAmount = 0
  let topBuy = { name: '', amount: 0 }
  let topSell = { name: '', amount: 0 }

  tableData.value.forEach(item => {
    totalAmount += (item.total_amount || 0)
    if (item.net_buy > topBuy.amount) {
      topBuy = { name: item.name, amount: item.net_buy }
    }
    if (item.net_buy < topSell.amount) {
      topSell = { name: item.name, amount: item.net_buy }
    }
  })

  return { totalAmount, topBuy, topSell }
})

async function loadData(resetPage = true) {
  if (resetPage) currentPage.value = 1
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    const { dateRange, code } = currentFilter.value
    if (dateRange) {
      params.start_date = dateRange[0]
      params.end_date = dateRange[1]
    }
    if (code) {
      params.code = normalizeCode(code)
    }
    const res = await dragonTigerApi.getDragonTiger(params)
    tableData.value = res.data?.data || []
    total.value = res.data?.total ?? tableData.value.length
  } catch {
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onSearch(filter: { dateRange: [string, string] | null, code: string }) {
  currentFilter.value = filter
  loadData(true)
}

function onPageChange(page: number) {
  currentPage.value = page
  loadData(false)
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  loadData(true)
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.dragon-tiger {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.overview-panel {
  margin-bottom: 4px;
}
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}
.stat-title {
  font-size: 13px;
  color: var(--text-muted, #909399);
  margin-bottom: 8px;
}
.stat-value {
  font-size: 20px;
  font-weight: bold;
  color: var(--text-primary, #303133);
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.stat-value.danger {
  color: var(--el-color-danger, #f56c6c);
}
.stat-value.success {
  color: var(--el-color-success, #67c23a);
}
.sub-value {
  font-size: 14px;
  font-weight: normal;
  color: var(--text-regular, #606266);
}
</style>
