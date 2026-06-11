<template>
  <div class="margin-trading">
    <!-- Filters -->
    <el-card shadow="never" class="section-card">
      <div class="filter-bar">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY年MM月DD日"
          value-format="YYYY-MM-DD"
          size="small"
          style="width:280px"
        />
        <el-button type="primary" size="small" @click="loadData">
          <el-icon><Search /></el-icon> 查询
        </el-button>
        <el-text size="small" type="info">融资融券为全市场汇总数据</el-text>
      </div>
    </el-card>

    <!-- Balance chart -->
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header><span>融资余额趋势</span></template>
      <div v-if="chartData.length > 0">
        <v-chart :option="lineOption" style="height:300px" autoresize />
      </div>
      <el-empty v-else-if="!loading" description="暂无数据" :image-size="60" />
    </el-card>

    <!-- Table -->
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header>
        <span>融资融券明细（共 {{ tableData.length }} 条）</span>
      </template>
      <el-empty v-if="tableData.length === 0 && !loading" description="暂无融资融券数据" />
      <el-table v-else :data="paginatedMargin" stripe size="small">
        <el-table-column prop="date" label="日期" width="120" sortable />
        <el-table-column label="融资余额" width="130" prop="rz_balance" sortable>
          <template #default="{ row }">{{ fmtAmount(row.rz_balance) }}</template>
        </el-table-column>
        <el-table-column label="融资买入" width="130" prop="rz_buy" sortable>
          <template #default="{ row }">{{ fmtAmount(row.rz_buy) }}</template>
        </el-table-column>
        <el-table-column label="融券量" width="120" prop="rq_volume" sortable>
          <template #default="{ row }">{{ fmtAmount(row.rq_volume) }}</template>
        </el-table-column>
        <el-table-column label="融券卖出" width="130" prop="rq_sell" sortable>
          <template #default="{ row }">{{ fmtAmount(row.rq_sell) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="tableData.length > pageSize"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="tableData.length"
        layout="total, sizes, prev, pager, next"
        background
        class="table-pagination"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { marginApi } from '@/api/margin'
import { fmtAmount } from '@/utils/format'
import type { MarginRecord } from '@/types'
import { Search } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const loading = ref(false)
const tableData = ref<MarginRecord[]>([])
const currentPage = ref(1)
const pageSize = ref(50)
const paginatedMargin = computed(() =>
  tableData.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value)
)
watch(tableData, () => { currentPage.value = 1 })
const dateRange = ref<[string, string]>([
  dayjs().subtract(6, 'month').format('YYYY-MM-DD'),
  dayjs().format('YYYY-MM-DD'),
])

const chartData = computed(() => {
  return [...tableData.value].sort((a, b) => a.date.localeCompare(b.date))
})

const lineOption = computed(() => {
  const sorted = chartData.value
  const dates = sorted.map(d => d.date)
  const balances = sorted.map(d => d.rz_balance)
  return {
    backgroundColor: '#1f1f1f',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#2c2c2c',
      borderColor: '#444',
      textStyle: { color: '#e5eaf3' },
    },
    grid: { left: 80, right: 20, top: 30, bottom: 60 },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, height: 20, bottom: 5 },
    ],
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        color: '#909399',
        rotate: 30,
        fontSize: 10,
        // 最多显示 8 个标签，避免密集重叠
        interval: Math.max(0, Math.floor(dates.length / 8) - 1),
      },
      axisLine: { lineStyle: { color: '#444' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#909399',
        formatter: (v: number) => (v >= 1e8 ? `${(v / 1e8).toFixed(1)}亿` : `${(v / 1e4).toFixed(0)}万`),
      },
      splitLine: { lineStyle: { color: '#2c2c2c' } },
    },
    series: [
      {
        name: '融资余额',
        type: 'line',
        data: balances,
        smooth: true,
        lineStyle: { color: '#409eff', width: 2 },
        areaStyle: { color: 'rgba(64,158,255,0.1)' },
        showSymbol: false,
      },
    ],
  }
})

async function loadData() {
  loading.value = true
  try {
    const params: { start_date?: string; end_date?: string; limit?: number } = {}
    if (dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
      const days = dayjs(dateRange.value[1]).diff(dayjs(dateRange.value[0]), 'day')
      params.limit = Math.max(300, days)
    }
    const res = await marginApi.getMargin(params)
    tableData.value = res.data?.data || res.data || []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.margin-trading {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.section-card :deep(.el-card__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 16px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.table-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.table-pagination :deep(.el-pagination__total),
.table-pagination :deep(.el-pagination__sizes .el-select .el-input__wrapper) {
  color: var(--text-muted);
}
</style>
