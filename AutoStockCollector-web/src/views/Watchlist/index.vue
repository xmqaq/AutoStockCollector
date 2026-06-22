<template>
  <div class="watchlist">
    <div class="wl-layout">
      <!-- 左侧分组栏 -->
      <div class="wl-sidebar">
        <div class="wl-sidebar-header">
          <span>分组</span>
          <el-button size="small" circle @click="showGroupDialog = true">
            <el-icon><Plus /></el-icon>
          </el-button>
        </div>
        <el-menu :default-active="activeGroup" @select="onGroupSelect" class="wl-group-menu">
          <el-menu-item index="__all__">
            <el-icon><FolderOpened /></el-icon>
            <span>全部 ({{ totalCount }})</span>
          </el-menu-item>
          <el-menu-item v-for="g in groups" :key="g.group_id" :index="g.group_id">
            <el-icon><Folder /></el-icon>
            <span>{{ g.name || g.group_id }} ({{ g.stock_count }})</span>
            <el-button v-if="g.group_id !== 'default'" size="small" text type="danger"
              class="wl-del-group" @click.stop="handleDeleteGroup(g.group_id)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </el-menu-item>
        </el-menu>
      </div>

      <!-- 右侧主区域 -->
      <div class="wl-main">
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="card-header">
              <span>{{ activeGroupName }}</span>
              <div class="card-header-actions">
                <el-button v-if="selectedCodes.length > 0" size="small" type="danger" plain @click="handleBatchRemove">
                  删除选中 ({{ selectedCodes.length }})
                </el-button>
                <el-button size="small" @click="showAddModal = true" type="primary">
                  <el-icon><Plus /></el-icon> 添加
                </el-button>
              </div>
            </div>
          </template>
          <el-empty v-if="list.length === 0 && !loading" description="暂无自选股" />
          <el-table v-else ref="tableRef" :data="list" stripe v-loading="loading"
            @selection-change="onSelectionChange" row-key="code" :row-class-name="rowClassName"
            @dragover.prevent @drop="onRowDrop" @dragend="onDragEnd">
            <el-table-column type="selection" width="36" />
            <el-table-column label="排序" width="40" align="center">
              <template #default>
                <el-icon class="wl-drag-handle" draggable="true" @dragstart="onDragStart"><Rank /></el-icon>
              </template>
            </el-table-column>
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
                <span v-if="row.change_rate !== null"
                  :style="{ color: (row.change_rate || 0) >= 0 ? RISE_COLOR : FALL_COLOR }">
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
            <el-table-column label="分组" width="100" align="center">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(gid: string) => handleMoveStock(row.code, gid)">
                  <el-button size="small" text>
                    {{ row.group_name || '未分组' }} <el-icon><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-for="g in groups" :key="g.group_id" :command="g.group_id"
                        :class="{ 'is-active': row.group_id === g.group_id }">
                        <el-icon v-if="row.group_id === g.group_id"><Check /></el-icon>
                        {{ g.name || g.group_id }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80" align="center" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="danger" plain @click="handleRemove(row.code)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </div>

    <!-- 添加自选 -->
    <el-dialog v-model="showAddModal" title="添加自选股" width="400px">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="股票代码">
          <StockSearch v-model="addForm.code" @search="(c) => addForm.code = c" />
        </el-form-item>
        <el-form-item label="所属分组">
          <el-select v-model="addForm.group_id" placeholder="选择分组" clearable>
            <el-option v-for="g in groups" :key="g.group_id" :label="g.name || g.group_id" :value="g.group_id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddModal = false">取消</el-button>
        <el-button type="primary" @click="handleAdd" :loading="addLoading">添加</el-button>
      </template>
    </el-dialog>

    <!-- 分组管理 -->
    <el-dialog v-model="showGroupDialog" title="新建分组" width="360px">
      <el-form :model="groupForm" label-width="70px">
        <el-form-item label="分组ID">
          <el-input v-model="groupForm.group_id" placeholder="英文/数字标识" />
        </el-form-item>
        <el-form-item label="分组名称">
          <el-input v-model="groupForm.name" placeholder="显示名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="groupForm.description" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGroupDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateGroup" :loading="groupLoading">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, FolderOpened, Folder, Rank, ArrowDown, Check } from '@element-plus/icons-vue'
import { watchlistApi, type WatchlistGroup } from '@/api/watchlist'
import { marketApi } from '@/api/market'
import type { StockQuote } from '@/api/market'
import { fmtNumber, fmtChange, fmtAmount, RISE_COLOR, FALL_COLOR } from '@/utils/format'
import type { WatchlistItem } from '@/types'
import StockSearch from '@/components/StockSearch/index.vue'

const router = useRouter()
const loading = ref(false)
const addLoading = ref(false)
const groupLoading = ref(false)
const showAddModal = ref(false)
const showGroupDialog = ref(false)
const list = ref<WatchlistItem[]>([])
const groups = ref<WatchlistGroup[]>([])
const activeGroup = ref('__all__')
const selectedCodes = ref<string[]>([])
const tableRef = ref<any>(null)
const dragCode = ref<string | null>(null)

const addForm = ref({ code: '', group_id: '' })
const groupForm = ref({ group_id: '', name: '', description: '' })

const totalCount = computed(() => list.value.length)
const activeGroupName = computed(() => {
  if (activeGroup.value === '__all__') return '全部自选'
  const g = groups.value.find(g => g.group_id === activeGroup.value)
  return g ? (g.name || g.group_id) : '自选股'
})

function goToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
}

function fmtVolume(volume: number): string {
  if (!volume) return '--'
  if (volume >= 1e8) return (volume / 1e8).toFixed(2) + '亿'
  if (volume >= 1e4) return (volume / 1e4).toFixed(2) + '万'
  return volume.toFixed(0)
}

function onSelectionChange(rows: WatchlistItem[]) {
  selectedCodes.value = rows.map(r => r.code)
}

function onGroupSelect(idx: string) {
  activeGroup.value = idx
  loadData()
}

function onDragStart(e: DragEvent) {
  const icon = (e.target as HTMLElement)?.closest?.('.wl-drag-handle')
  if (!icon) return
  const row = icon.closest<HTMLElement>('[data-code]')
  if (row) {
    dragCode.value = row.getAttribute('data-code')
    e.dataTransfer?.setData('text/plain', dragCode.value || '')
  }
}

function onDragEnd() {
  dragCode.value = null
}

function rowClassName({ row }: { row: WatchlistItem }) {
  return `wl-row-${row.code}`
}

async function onRowDrop(e: DragEvent) {
  const targetRow = (e.target as HTMLElement)?.closest?.('[data-code]')
  const targetCode = targetRow?.getAttribute('data-code')
  if (!dragCode.value || !targetCode || dragCode.value === targetCode) return
  const items = [...list.value]
  const fromIdx = items.findIndex(i => i.code === dragCode.value)
  const toIdx = items.findIndex(i => i.code === targetCode)
  if (fromIdx === -1 || toIdx === -1) return
  const [moved] = items.splice(fromIdx, 1)
  items.splice(toIdx, 0, moved)
  list.value = items
  const priorities = list.value.map((item, idx) => ({ code: item.code, priority: (items.length - idx) * 10 }))
  for (const p of priorities) {
    watchlistApi.updatePriority(p.code, p.priority).catch(() => {})
  }
  dragCode.value = null
}

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

onMounted(() => loadData())
</script>

<style scoped>
.wl-layout { display: flex; gap: 16px; align-items: flex-start; }
.wl-sidebar { width: 200px; flex-shrink: 0; background: var(--bg-card); border-radius: 8px; border: 1px solid var(--border-color); overflow: hidden; }
.wl-sidebar-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-color); font-weight: 600; font-size: 14px; }
.wl-group-menu { border-right: none; }
.wl-del-group { margin-left: auto; opacity: 0.4; }
.wl-del-group:hover { opacity: 1; }
.wl-main { flex: 1; min-width: 0; }
.wl-drag-handle { cursor: grab; color: var(--text-secondary); opacity: 0.5; }
.wl-drag-handle:active { cursor: grabbing; opacity: 1; }
.section-card { background: var(--bg-card); border: 1px solid var(--border-color); }
.section-card :deep(.el-card__header) { border-bottom: 1px solid var(--border-color); padding: 12px 16px; color: var(--text-primary); font-size: 14px; font-weight: 600; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-header-actions { display: flex; gap: 8px; }
.code-link { color: var(--el-color-primary); cursor: pointer; }
.code-link:hover { color: #79bbff; }
.text-muted { color: var(--text-faint); font-size: 12px; }
.is-active .el-icon { color: var(--el-color-primary); }

@media (max-width: 900px) {
  .wl-layout { flex-direction: column; }
  .wl-sidebar { width: 100%; }
}
</style>
