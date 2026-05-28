<template>
  <div class="dragon-tiger">
    <!-- Filters -->
    <el-card shadow="never" class="section-card">
      <div class="filter-bar">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          size="small"
          style="width:280px"
        />
        <el-input
          v-model="codeFilter"
          placeholder="股票代码（可选）"
          size="small"
          style="width:200px"
          clearable
        />
        <el-button type="primary" size="small" @click="loadData">
          <el-icon><Search /></el-icon> 查询
        </el-button>
      </div>
    </el-card>

    <!-- Table -->
    <el-card shadow="never" class="section-card" v-loading="loading">
      <template #header>
        <span>龙虎榜数据（共 {{ tableData.length }} 条）</span>
      </template>
      <el-empty v-if="tableData.length === 0 && !loading" description="暂无龙虎榜数据" />
      <el-table v-else :data="tableData" stripe>
        <el-table-column prop="date" label="日期" width="120" sortable />
        <el-table-column prop="code" label="代码" width="110">
          <template #default="{ row }">
            <el-link type="primary" @click="goToStock(row.code)">{{ row.code }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column prop="reason" label="上榜原因" min-width="200" show-overflow-tooltip />
        <el-table-column label="上榜金额" width="130" sortable prop="total_amount">
          <template #default="{ row }">
            <span>{{ fmtAmount(row.total_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="净买入" width="130" sortable prop="net_buy">
          <template #default="{ row }">
            <span :style="{ color: row.net_buy >= 0 ? RISE_COLOR : FALL_COLOR }">
              {{ fmtAmount(row.net_buy) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { dragonTigerApi } from '@/api/dragonTiger'
import { fmtAmount, RISE_COLOR, FALL_COLOR } from '@/utils/format'
import { normalizeCode } from '@/utils/stockCode'
import type { DragonTigerRecord } from '@/types'
import { Search } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(false)
const tableData = ref<DragonTigerRecord[]>([])
const dateRange = ref<[string, string]>([
  dayjs().subtract(30, 'day').format('YYYY-MM-DD'),
  dayjs().format('YYYY-MM-DD'),
])
const codeFilter = ref('')

async function loadData() {
  loading.value = true
  try {
    const params: { start_date?: string; end_date?: string; code?: string; limit?: number } = {
      limit: 200,
    }
    if (dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    if (codeFilter.value) {
      params.code = normalizeCode(codeFilter.value)
    }
    const res = await dragonTigerApi.getDragonTiger(params)
    tableData.value = res.data?.data || res.data || []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
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

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
</style>
