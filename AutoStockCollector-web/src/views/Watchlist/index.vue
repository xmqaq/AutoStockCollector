<template>
  <div class="watchlist-page">
    <div class="wl-layout">
      <!-- 左侧分组栏 -->
      <WatchlistSidebar 
        :groups="groups"
        v-model:activeGroup="activeGroup"
        :totalCount="totalCount"
        @add-group="showGroupDialog = true"
        @delete-group="handleDeleteGroup"
      />

      <!-- 右侧主区域 -->
      <div class="wl-main">
        <WatchlistTable 
          :list="list"
          :groups="groups"
          :loading="loading"
          :activeGroupName="activeGroupName"
          v-model:selectedCodes="selectedCodes"
          @batch-remove="handleBatchRemove"
          @add-stock="showAddModal = true"
          @remove-stock="handleRemove"
          @move-stock="handleMoveStock"
          @update-priority="handleUpdatePriority"
        />
      </div>
    </div>

    <!-- 弹窗组件 -->
    <WatchlistDialogs 
      v-model:showAddModal="showAddModal"
      v-model:showGroupDialog="showGroupDialog"
      :addLoading="addLoading"
      :groupLoading="groupLoading"
      :groups="groups"
      :addForm="addForm"
      :groupForm="groupForm"
      @submit-add="handleAdd"
      @submit-group="handleCreateGroup"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { watchlistApi, type WatchlistGroup } from '@/api/watchlist'
import { marketApi } from '@/api/market'
import type { StockQuote } from '@/api/market'
import type { WatchlistItem } from '@/types'

import WatchlistSidebar from './components/WatchlistSidebar.vue'
import WatchlistTable from './components/WatchlistTable.vue'
import WatchlistDialogs from './components/WatchlistDialogs.vue'

const loading = ref(false)
const addLoading = ref(false)
const groupLoading = ref(false)
const showAddModal = ref(false)
const showGroupDialog = ref(false)
const list = ref<WatchlistItem[]>([])
const groups = ref<WatchlistGroup[]>([])
const activeGroup = ref('__all__')
const selectedCodes = ref<string[]>([])

const addForm = ref({ code: '', group_id: '' })
const groupForm = ref({ group_id: '', name: '', description: '' })

const totalCount = computed(() => list.value.length)
const activeGroupName = computed(() => {
  if (activeGroup.value === '__all__') return '全部自选'
  const g = groups.value.find(g => g.group_id === activeGroup.value)
  return g ? (g.name || g.group_id) : '自选股'
})

async function loadData() {
  loading.value = true
  try {
    const groupId = activeGroup.value === '__all__' ? undefined : activeGroup.value
    const [wlRes, grpRes] = await Promise.all([
      watchlistApi.getWatchlist(groupId),
      watchlistApi.getGroups(),
    ])
    const watchlist: WatchlistItem[] = wlRes.data?.data || wlRes.data || []
    groups.value = grpRes.data?.data || []

    if (watchlist.length > 0) {
      const codes = watchlist.map(s => s.code)
      const quotesRes = await marketApi.getRealtimeQuotes(codes)
      const quotes: StockQuote[] = quotesRes.data?.data || []
      const quotesMap = new Map(quotes.map((q: StockQuote) => [q.code, q]))

      const groupMap = new Map(groups.value.map(g => [g.group_id, g.name || g.group_id]))
      list.value = watchlist.map(s => ({
        ...s,
        latest_price: s.latest_price ?? null,
        change_rate: s.change_rate ?? null,
        turnover_rate: s.turnover_rate ?? null,
        volume: s.volume ?? null,
        turnover: s.turnover ?? null,
        group_name: s.group_id ? (groupMap.get(s.group_id) || s.group_id) : '未分组',
      }))
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
    const data: any = { code: addForm.value.code }
    if (addForm.value.group_id) data.group_id = addForm.value.group_id
    const res = await watchlistApi.addWatchlist(data)
    if (res.data?.success !== false) {
      ElMessage.success('添加成功')
      showAddModal.value = false
      addForm.value = { code: '', group_id: '' }
      await loadData()
    }
  } finally {
    addLoading.value = false
  }
}

async function handleRemove(code: string) {
  try {
    await ElMessageBox.confirm(`确定删除 ${code} 吗？`, '删除确认', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await watchlistApi.removeWatchlist(code)
    ElMessage.success('已删除')
    await loadData()
  } catch { /* cancelled */ }
}

async function handleBatchRemove() {
  if (selectedCodes.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedCodes.value.length} 只股票吗？`, '批量删除', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await watchlistApi.batchRemove(selectedCodes.value)
    ElMessage.success(`已删除 ${selectedCodes.value.length} 只`)
    selectedCodes.value = []
    await loadData()
  } catch { /* cancelled */ }
}

async function handleMoveStock(code: string, groupId: string) {
  try {
    await watchlistApi.moveStock(code, groupId)
    ElMessage.success('移动成功')
    await loadData()
  } catch {
    ElMessage.error('移动失败')
  }
}

async function handleCreateGroup() {
  if (!groupForm.value.group_id) {
    ElMessage.warning('请输入分组ID')
    return
  }
  groupLoading.value = true
  try {
    await watchlistApi.createGroup(groupForm.value.group_id, groupForm.value.name || groupForm.value.group_id, groupForm.value.description)
    ElMessage.success('分组已创建')
    showGroupDialog.value = false
    groupForm.value = { group_id: '', name: '', description: '' }
    await loadData()
  } finally {
    groupLoading.value = false
  }
}

async function handleDeleteGroup(groupId: string) {
  try {
    await ElMessageBox.confirm('删除分组后，组内股票将被隐藏。确定删除吗？', '删除分组', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await watchlistApi.deleteGroup(groupId)
    ElMessage.success('分组已删除')
    if (activeGroup.value === groupId) activeGroup.value = '__all__'
    await loadData()
  } catch { /* cancelled */ }
}

async function handleUpdatePriority(items: WatchlistItem[]) {
  list.value = items
  const priorities = items.map((item, idx) => ({ code: item.code, priority: (items.length - idx) * 10 }))
  for (const p of priorities) {
    watchlistApi.updatePriority(p.code, p.priority).catch(() => {})
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.watchlist-page {
  padding: 24px 32px;
  background-color: var(--el-bg-color-page);
  min-height: calc(100vh - 60px);
  box-sizing: border-box;
}

.wl-layout { 
  display: flex; 
  gap: 24px; 
  align-items: flex-start; 
  max-width: 1600px;
  margin: 0 auto;
}

.wl-main { 
  flex: 1; 
  min-width: 0; 
}

@media (max-width: 900px) {
  .wl-layout { flex-direction: column; }
  .wl-sidebar { width: 100%; }
}
</style>
