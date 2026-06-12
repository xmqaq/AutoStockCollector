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
          format="YYYY年MM月DD日"
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
        <span>龙虎榜数据（共 {{ total }} 条）</span>
      </template>
      <el-empty v-if="tableData.length === 0 && !loading" description="暂无龙虎榜数据" />
      <el-table v-else :data="tableData" stripe>
        <el-table-column prop="date" label="日期" width="120" sortable />
        <el-table-column prop="code" label="代码" width="110">
          <template #default="{ row }">
            <span class="code-link" @click="goToStock(row.code)">{{ row.code }}</span>
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
        <el-table-column label="涨跌幅" width="100" sortable prop="change_rate">
          <template #default="{ row }">
            <span v-if="row.change_rate !== undefined && row.change_rate !== 0"
              :style="{ color: row.change_rate >= 0 ? RISE_COLOR : FALL_COLOR }">
              {{ fmtChange(row.change_rate) }}
            </span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column label="收盘价" width="100" prop="close">
          <template #default="{ row }">
            {{ row.close ? fmtNumber(row.close) : '--' }}
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="total > 0"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100, 200]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        background
        class="table-pagination"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { dragonTigerApi } from '@/api/dragonTiger'
import { fmtAmount, fmtChange, fmtNumber, RISE_COLOR, FALL_COLOR } from '@/utils/format'
import { normalizeCode } from '@/utils/stockCode'
import type { DragonTigerRecord } from '@/types'
import { Search } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

const router = useRouter()
const loading = ref(false)
const tableData = ref<DragonTigerRecord[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(50)
const dateRange = ref<[string, string] | null>(null)
const codeFilter = ref('')

async function loadData(resetPage = true) {
  if (resetPage) currentPage.value = 1
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (dateRange.value) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    if (codeFilter.value) {
      params.code = normalizeCode(codeFilter.value)
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

function onPageChange(page: number) {
  currentPage.value = page
  loadData(false)
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  loadData(true)
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

.code-link {
  color: var(--el-color-primary);
  cursor: pointer;
}
.code-link:hover {
  color: #79bbff;
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
