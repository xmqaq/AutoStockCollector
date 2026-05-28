<template>
  <div class="sector-flow">
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>板块流向（快照数据）</span>
          <el-button size="small" @click="loadData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <el-empty v-if="sectors.length === 0 && !loading" description="暂无板块数据" />
      <v-chart
        v-else-if="sectors.length > 0"
        :option="treemapOption"
        style="height:500px"
        autoresize
        @click="handleSectorClick"
      />
    </el-card>

    <!-- Sector stocks drawer -->
    <el-drawer
      v-model="drawerVisible"
      :title="`${selectedSector} - 成分股`"
      direction="rtl"
      size="500px"
    >
      <div v-loading="stocksLoading">
        <el-empty v-if="sectorStocks.length === 0 && !stocksLoading" description="暂无成分股数据" />
        <el-table v-else :data="sectorStocks" stripe size="small">
          <el-table-column prop="code" label="代码" width="110">
            <template #default="{ row }">
              <el-link type="primary" @click="goToStock(row.code || row)">{{ row.code || row }}</el-link>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" />
          <el-table-column label="涨跌幅" width="100">
            <template #default="{ row }">
              <span v-if="row.change_rate !== undefined" :style="{ color: row.change_rate >= 0 ? RISE_COLOR : FALL_COLOR }">
                {{ fmtChange(row.change_rate) }}
              </span>
              <span v-else>--</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>

    <!-- Sector list -->
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header><span>板块列表</span></template>
      <el-empty v-if="sectors.length === 0 && !loading" description="暂无板块数据" />
      <el-table v-else :data="paginatedSectors" stripe size="small">
        <el-table-column prop="name" label="板块名称" min-width="180">
          <template #default="{ row }">
            <el-link type="primary" @click="loadSectorStocks(row.name)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="净流入" width="130" prop="net_flow" sortable>
          <template #default="{ row }">
            <span :style="{ color: (row.net_flow || 0) >= 0 ? RISE_COLOR : FALL_COLOR }">
              {{ fmtAmount(row.net_flow || 0) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="100" prop="change_rate" sortable>
          <template #default="{ row }">
            <span :style="{ color: (row.change_rate || 0) >= 0 ? RISE_COLOR : FALL_COLOR }">
              {{ fmtChange(row.change_rate || 0) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="sectors.length > pageSize"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="sectors.length"
        layout="total, sizes, prev, pager, next"
        background
        class="table-pagination"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { TreemapChart } from 'echarts/charts'
import { TooltipComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { sectorApi } from '@/api/sector'
import { fmtAmount, fmtChange, RISE_COLOR, FALL_COLOR } from '@/utils/format'
import type { SectorRecord } from '@/types'
import { Refresh } from '@element-plus/icons-vue'

use([TreemapChart, TooltipComponent, TitleComponent, CanvasRenderer])

const router = useRouter()
const loading = ref(false)
const stocksLoading = ref(false)
const sectors = ref<SectorRecord[]>([])
const currentPage = ref(1)
const pageSize = ref(50)
const paginatedSectors = computed(() =>
  sectors.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value)
)
watch(sectors, () => { currentPage.value = 1 })
const drawerVisible = ref(false)
const selectedSector = ref('')
const sectorStocks = ref<unknown[]>([])

const treemapOption = computed(() => {
  const data = sectors.value.map(s => ({
    name: s.name,
    value: Math.abs(s.net_flow || s.change_rate || 1),
    itemStyle: {
      color: (s.net_flow || 0) >= 0 ? RISE_COLOR : FALL_COLOR,
      opacity: Math.min(1, 0.4 + Math.abs(s.change_rate || 0) / 10),
    },
    label: {
      show: true,
      formatter: (p: { data: { name: string; sectorData: SectorRecord } }) => {
        const sr = p.data.sectorData
        return `${p.data.name}\n${fmtChange(sr?.change_rate || 0)}`
      },
    },
    sectorData: s,
  }))

  return {
    backgroundColor: '#1f1f1f',
    tooltip: {
      formatter: (p: { data: { name: string; sectorData: SectorRecord } }) => {
        const s = p.data.sectorData
        if (!s) return p.data.name
        return `
          <b>${s.name}</b><br/>
          净流入: ${fmtAmount(s.net_flow || 0)}<br/>
          涨跌幅: ${fmtChange(s.change_rate || 0)}
        `
      },
    },
    series: [
      {
        type: 'treemap',
        data,
        width: '100%',
        height: '100%',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: {
          show: true,
          color: '#fff',
          fontSize: 12,
        },
      },
    ],
  }
})

async function loadData() {
  loading.value = true
  try {
    const res = await sectorApi.getSectors()
    sectors.value = res.data?.data || res.data || []
  } catch {
    sectors.value = []
  } finally {
    loading.value = false
  }
}

async function loadSectorStocks(name: string) {
  selectedSector.value = name
  drawerVisible.value = true
  stocksLoading.value = true
  try {
    const res = await sectorApi.getSectorStocks(name)
    sectorStocks.value = res.data?.data || res.data || []
  } catch {
    sectorStocks.value = []
  } finally {
    stocksLoading.value = false
  }
}

function handleSectorClick(params: unknown) {
  const p = params as { data?: { name?: string } }
  if (p.data?.name) {
    loadSectorStocks(p.data.name)
  }
}

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
  drawerVisible.value = false
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.sector-flow {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid #2c2c2c;
  padding: 12px 16px;
  color: #e5eaf3;
  font-size: 14px;
  font-weight: 600;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.table-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.table-pagination :deep(.el-pagination__total),
.table-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  color: #909399;
}
</style>
