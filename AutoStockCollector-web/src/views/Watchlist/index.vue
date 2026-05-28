<template>
  <div class="watchlist">
    <!-- Add stock -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>自选股管理</span>
          <el-button size="small" @click="showAddModal = true" type="primary">
            <el-icon><Plus /></el-icon> 添加自选
          </el-button>
        </div>
      </template>
      <div class="group-tabs" v-if="groups.length > 0">
        <el-tabs v-model="activeGroup">
          <el-tab-pane label="全部" name="all" />
          <el-tab-pane
            v-for="g in groups"
            :key="g.id"
            :label="g.name"
            :name="g.id"
          />
        </el-tabs>
      </div>
      <el-empty v-if="filteredList.length === 0 && !loading" description="暂无自选股，点击添加" />
      <el-table v-else :data="filteredList" stripe v-loading="loading">
        <el-table-column prop="code" label="代码" width="120">
          <template #default="{ row }">
            <el-link type="primary" @click="goToStock(row.code)">{{ row.code }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="group_id" label="分组" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ groupName(row.group_id) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100" sortable />
        <el-table-column prop="added_at" label="添加时间" min-width="160">
          <template #default="{ row }">{{ fmtDateTime(row.added_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button
              size="small"
              type="danger"
              plain
              @click="handleRemove(row.code)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Add modal -->
    <el-dialog v-model="showAddModal" title="添加自选股" width="400px">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="股票代码">
          <StockSearch v-model="addForm.code" @search="(c) => addForm.code = c" />
        </el-form-item>
        <el-form-item label="分组">
          <el-select v-model="addForm.group_id" clearable placeholder="默认分组" style="width:100%">
            <el-option
              v-for="g in groups"
              :key="g.id"
              :label="g.name"
              :value="g.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="addForm.priority" :min="0" :max="100" style="width:100%" />
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { watchlistApi } from '@/api/watchlist'
import { fmtDateTime } from '@/utils/format'
import type { WatchlistItem, WatchlistGroup } from '@/types'
import StockSearch from '@/components/StockSearch/index.vue'
import { Plus } from '@element-plus/icons-vue'

const router = useRouter()
const loading = ref(false)
const addLoading = ref(false)
const showAddModal = ref(false)
const watchlist = ref<WatchlistItem[]>([])
const groups = ref<WatchlistGroup[]>([])
const activeGroup = ref('all')

const addForm = ref({
  code: '',
  group_id: '',
  priority: 0,
})

const filteredList = computed(() => {
  if (activeGroup.value === 'all') return watchlist.value
  return watchlist.value.filter(w => w.group_id === activeGroup.value)
})

function groupName(id?: string): string {
  if (!id) return '默认'
  const g = groups.value.find(g => g.id === id)
  return g?.name || id
}

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
}

async function loadData() {
  loading.value = true
  try {
    const [wRes, gRes] = await Promise.all([
      watchlistApi.getWatchlist(),
      watchlistApi.getGroups(),
    ])
    watchlist.value = wRes.data?.data || wRes.data || []
    groups.value = gRes.data?.groups || gRes.data?.data || gRes.data || []
  } catch {
    watchlist.value = []
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
    const payload: { code: string; group_id?: string; priority?: number } = {
      code: addForm.value.code,
    }
    if (addForm.value.group_id) payload.group_id = addForm.value.group_id
    if (addForm.value.priority > 0) payload.priority = addForm.value.priority

    const res = await watchlistApi.addWatchlist(payload)
    if (res.data?.success !== false) {
      ElMessage.success('添加成功')
      showAddModal.value = false
      addForm.value = { code: '', group_id: '', priority: 0 }
      await loadData()
    }
  } finally {
    addLoading.value = false
  }
}

async function handleRemove(code: string) {
  try {
    await ElMessageBox.confirm(`确定要删除 ${code} 吗？`, '删除确认', {
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

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.watchlist {
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

.group-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.group-tabs :deep(.el-tabs__nav-wrap::after) {
  background: #2c2c2c;
}
</style>
