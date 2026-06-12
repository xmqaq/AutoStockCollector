<template>
  <div class="watchlist">
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>自选股</span>
          <el-button size="small" @click="showAddModal = true" type="primary">
            <el-icon><Plus /></el-icon> 添加
          </el-button>
        </div>
      </template>
      <el-empty v-if="list.length === 0 && !loading" description="暂无自选股" />
      <el-table v-else :data="list" stripe v-loading="loading">
        <el-table-column prop="code" label="代码" width="110">
          <template #default="{ row }">
            <span class="code-link" @click="goToStock(row.code)">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column label="最新价" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.latest_price">{{ fmtNumber(row.latest_price) }}</span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅" width="90" align="center">
          <template #default="{ row }">
            <span
              v-if="row.change_rate !== null"
              :style="{ color: (row.change_rate || 0) >= 0 ? RISE_COLOR : FALL_COLOR }"
            >
              {{ fmtChange(row.change_rate) }}
            </span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="换手率" width="80" align="right">
          <template #default="{ row }">
            <span v-if="row.turnover_rate !== null">{{ row.turnover_rate?.toFixed(2) }}%</span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="成交量" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.volume">{{ fmtVolume(row.volume) }}</span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="成交额" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.turnover">{{ fmtAmount(row.turnover) }}</span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button size="small" type="danger" plain @click="handleRemove(row.code)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showAddModal" title="添加自选股" width="380px">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="股票代码">
          <StockSearch v-model="addForm.code" @search="(c) => addForm.code = c" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddModal = false">取消</el-button>
        <el-button type="primary" @click="handleAdd" :loading="addLoading">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { watchlistApi } from '@/api/watchlist'
import { marketApi } from '@/api/market'
import type { StockQuote } from '@/api/market'
import { fmtNumber, fmtChange, fmtAmount, RISE_COLOR, FALL_COLOR } from '@/utils/format'
import type { WatchlistItem } from '@/types'
import StockSearch from '@/components/StockSearch/index.vue'
import { Plus } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const addLoading = ref(false)
const showAddModal = ref(false)
const list = ref<WatchlistItem[]>([])

const addForm = ref({ code: '' })

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
}

function fmtVolume(volume: number): string {
  if (!volume) return '--'
  if (volume >= 1e8) return (volume / 1e8).toFixed(2) + '亿'
  if (volume >= 1e4) return (volume / 1e4).toFixed(2) + '万'
  return volume.toFixed(0)
}

async function loadData() {
  loading.value = true
  try {
    const res = await watchlistApi.getWatchlist()
    const watchlist: WatchlistItem[] = res.data?.data || res.data || []
    
    if (watchlist.length > 0) {
      const codes = watchlist.map(s => s.code)
      const quotesRes = await marketApi.getRealtimeQuotes(codes)
      const quotes: StockQuote[] = quotesRes.data?.data || []
      const quotesMap = new Map(quotes.map((q: StockQuote) => [q.code, q]))
      
      list.value = watchlist.map(s => {
        const quote = quotesMap.get(s.code)
        return {
          ...s,
          latest_price: quote?.price ?? null,
          change_rate: quote?.change ?? null,
          turnover_rate: quote?.turnover ?? null,
          volume: quote?.volume ?? null,
          turnover: quote?.amount ?? null,
        }
      })
    } else {
      list.value = []
    }
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

async function handleAdd() {
  if (!addForm.value.code) {
    ElMessage.warning('请输入股票代码')
    return
  }
  addLoading.value = true
  try {
    const res = await watchlistApi.addWatchlist({ code: addForm.value.code })
    if (res.data?.success !== false) {
      ElMessage.success('添加成功')
      showAddModal.value = false
      addForm.value = { code: '' }
      await loadData()
    }
  } finally {
    addLoading.value = false
  }
}

async function handleRemove(code: string) {
  try {
    await ElMessageBox.confirm(`确定删除 ${code} 吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await watchlistApi.removeWatchlist(code)
    ElMessage.success('已删除')
    await loadData()
  } catch {
    // cancelled
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.watchlist {
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

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.code-link {
  color: var(--el-color-primary);
  cursor: pointer;
}
.code-link:hover {
  color: #79bbff;
}

.text-muted {
  color: var(--text-faint);
  font-size: 12px;
}
</style>