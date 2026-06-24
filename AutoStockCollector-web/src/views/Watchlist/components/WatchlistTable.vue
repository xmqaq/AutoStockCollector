<template>
  <el-card shadow="never" class="section-card">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <span class="header-title">{{ activeGroupName }}</span>
          <el-tag type="info" size="small" effect="plain">{{ list.length }} 只</el-tag>
        </div>
        <div class="card-header-actions">
          <el-button v-if="selectedCodes.length > 0" size="small" type="danger" plain round @click="$emit('batch-remove')">
            删除选中 ({{ selectedCodes.length }})
          </el-button>
          <el-button size="small" type="primary" round @click="$emit('add-stock')">
            <el-icon><Plus /></el-icon> 添加自选
          </el-button>
        </div>
      </div>
    </template>

    <div v-if="list.length === 0 && !loading" class="empty-state">
      <el-empty description="该分组下暂无自选股" :image-size="120" />
    </div>

    <el-table 
      v-else 
      ref="tableRef" 
      :data="list" 
      stripe 
      v-loading="loading"
      @selection-change="onSelectionChange" 
      row-key="code" 
      :row-class-name="rowClassName"
      @dragover.prevent 
      @drop="onRowDrop" 
      @dragend="onDragEnd"
      class="custom-table"
      :header-cell-style="{ background: 'var(--el-fill-color-light)', color: 'var(--el-text-color-primary)', fontWeight: 600 }"
    >
      <el-table-column type="selection" width="46" align="center" />
      <el-table-column label="排序" width="50" align="center">
        <template #default>
          <el-icon class="wl-drag-handle" draggable="true" @dragstart="onDragStart"><Rank /></el-icon>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="代码" width="110">
        <template #default="{ row }">
          <span class="code-link" @click="goToStock(row.code)">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="120">
        <template #default="{ row }">
          <span class="stock-name">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="最新价" width="100" align="right">
        <template #default="{ row }">
          <span class="num-font" v-if="row.latest_price">{{ fmtNumber(row.latest_price) }}</span>
          <span v-else class="text-muted">--</span>
        </template>
      </el-table-column>
      <el-table-column label="涨跌幅" width="100" align="center">
        <template #default="{ row }">
          <span class="num-font font-bold" v-if="row.change_rate !== null"
            :style="{ color: (row.change_rate || 0) >= 0 ? RISE_COLOR : FALL_COLOR }">
            {{ fmtChange(row.change_rate) }}
          </span>
          <span v-else class="text-muted">--</span>
        </template>
      </el-table-column>
      <el-table-column label="换手率" width="90" align="right">
        <template #default="{ row }">
          <span class="num-font" v-if="row.turnover_rate !== null">{{ row.turnover_rate?.toFixed(2) }}%</span>
          <span v-else class="text-muted">--</span>
        </template>
      </el-table-column>
      <el-table-column label="成交量" width="110" align="right">
        <template #default="{ row }">
          <span class="num-font" v-if="row.volume">{{ fmtVolume(row.volume) }}</span>
          <span v-else class="text-muted">--</span>
        </template>
      </el-table-column>
      <el-table-column label="成交额" width="110" align="right">
        <template #default="{ row }">
          <span class="num-font" v-if="row.turnover">{{ fmtAmount(row.turnover) }}</span>
          <span v-else class="text-muted">--</span>
        </template>
      </el-table-column>
      <el-table-column label="所属分组" min-width="120" align="center">
        <template #default="{ row }">
          <el-dropdown trigger="click" @command="(gid: string) => $emit('move-stock', row.code, gid)">
            <el-button size="small" class="group-btn" text>
              {{ row.group_name || '未分组' }} <el-icon class="el-icon--right"><ArrowDown /></el-icon>
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
      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="danger" plain link @click="$emit('remove-stock', row.code)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Rank, ArrowDown, Check } from '@element-plus/icons-vue'
import type { WatchlistItem } from '@/types'
import type { WatchlistGroup } from '@/api/watchlist'
import { fmtNumber, fmtChange, fmtAmount, RISE_COLOR, FALL_COLOR } from '@/utils/format'

const props = defineProps<{
  list: WatchlistItem[]
  groups: WatchlistGroup[]
  loading: boolean
  activeGroupName: string
  selectedCodes: string[]
}>()

const emit = defineEmits<{
  (e: 'update:selectedCodes', codes: string[]): void
  (e: 'batch-remove'): void
  (e: 'add-stock'): void
  (e: 'remove-stock', code: string): void
  (e: 'move-stock', code: string, groupId: string): void
  (e: 'update-priority', list: WatchlistItem[]): void
}>()

const router = useRouter()
const tableRef = ref<any>(null)
const dragCode = ref<string | null>(null)

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
  emit('update:selectedCodes', rows.map(r => r.code))
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

function onRowDrop(e: DragEvent) {
  const targetRow = (e.target as HTMLElement)?.closest?.('[data-code]')
  const targetCode = targetRow?.getAttribute('data-code')
  if (!dragCode.value || !targetCode || dragCode.value === targetCode) return
  
  const items = [...props.list]
  const fromIdx = items.findIndex(i => i.code === dragCode.value)
  const toIdx = items.findIndex(i => i.code === targetCode)
  if (fromIdx === -1 || toIdx === -1) return
  
  const [moved] = items.splice(fromIdx, 1)
  items.splice(toIdx, 0, moved)
  
  emit('update-priority', items)
  dragCode.value = null
}
</script>

<style scoped>
.section-card { 
  border-radius: 16px;
  border: none;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  background: #fff;
}
.section-card :deep(.el-card__header) { 
  border-bottom: 1px solid var(--el-border-color-lighter); 
  padding: 16px 24px; 
}
.card-header { 
  display: flex; 
  align-items: center; 
  justify-content: space-between; 
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-title {
  font-size: 16px; 
  font-weight: 600; 
  color: var(--el-text-color-primary); 
}
.card-header-actions { 
  display: flex; 
  gap: 12px; 
}
.empty-state {
  padding: 60px 0;
}
.custom-table :deep(td.el-table__cell) {
  padding: 12px 0;
}
.wl-drag-handle { 
  cursor: grab; 
  color: var(--el-text-color-secondary); 
  opacity: 0.5; 
  font-size: 18px;
}
.wl-drag-handle:active { 
  cursor: grabbing; 
  opacity: 1; 
  color: var(--el-color-primary);
}
.code-link { 
  color: var(--el-color-primary); 
  cursor: pointer; 
  font-family: Monaco, Consolas, monospace;
  font-weight: 500;
}
.code-link:hover { 
  color: var(--el-color-primary-light-3); 
  text-decoration: underline;
}
.stock-name {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.num-font {
  font-family: Monaco, Consolas, monospace;
}
.font-bold {
  font-weight: bold;
}
.text-muted { 
  color: var(--el-text-color-placeholder); 
}
.group-btn {
  background-color: var(--el-fill-color-light);
  border-radius: 12px;
  padding: 4px 12px;
}
.is-active .el-icon { 
  color: var(--el-color-primary); 
}
</style>
