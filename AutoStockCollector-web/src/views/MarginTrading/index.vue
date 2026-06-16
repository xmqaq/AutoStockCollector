<template>
  <div class="margin-trading">
    <MarginFilter 
      :date-range="dateRange"
      @update:date-range="dateRange = $event"
      @search="loadData"
    />
    <MarginChart 
      :loading="loading"
      :data="tableData"
    />
    <MarginTable 
      :loading="loading"
      :data="tableData"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { marginApi } from '@/api/margin'
import type { MarginRecord } from '@/types'
import dayjs from 'dayjs'

import MarginFilter from './components/MarginFilter.vue'
import MarginChart from './components/MarginChart.vue'
import MarginTable from './components/MarginTable.vue'

const loading = ref(false)
const tableData = ref<MarginRecord[]>([])
const dateRange = ref<[string, string] | null>([
  dayjs().subtract(6, 'month').format('YYYY-MM-DD'),
  dayjs().format('YYYY-MM-DD'),
])

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
  gap: 12px;
  height: 100%;
  overflow: hidden;
}
</style>
