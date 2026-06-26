<template>
  <el-drawer
    :model-value="visible"
    direction="rtl"
    size="500px"
    class="sector-drawer"
    :with-header="false"
    @update:model-value="$emit('update:visible', $event)"
  >
    <div class="drawer-container">
      <div class="drawer-header">
        <div class="header-left">
          <el-icon class="header-icon"><Menu /></el-icon>
          <span class="header-title">{{ sectorName }}</span>
          <el-tag size="small" type="info" effect="plain" round class="count-tag">
            {{ stocks.length }}只成分股
          </el-tag>
        </div>
        <el-icon class="close-icon" @click="$emit('update:visible', false)"><Close /></el-icon>
      </div>

      <div v-loading="loading" class="drawer-content">
        <el-empty v-if="stocks.length === 0 && !loading" description="暂无成分股数据" />
        <el-table 
          v-else 
          :data="stocks" 
          stripe 
          size="default" 
          height="100%" 
          class="custom-table"
        >
          <el-table-column prop="code" label="代码" width="120">
            <template #default="{ row }">
              <span class="code-link" @click="handleGoToStock(row.code || row)">{{ row.code || row }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" />
          <el-table-column label="涨跌幅" width="120" align="right">
            <template #default="{ row }">
              <div class="change-cell">
                <span v-if="row.change_rate !== undefined" class="money-text" :class="row.change_rate >= 0 ? 'is-rise' : 'is-fall'">
                  <el-icon v-if="row.change_rate > 0" class="trend-icon"><CaretTop /></el-icon>
                  <el-icon v-if="row.change_rate < 0" class="trend-icon"><CaretBottom /></el-icon>
                  {{ fmtChange(row.change_rate) }}
                </span>
                <span v-else class="money-text text-muted">--</span>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Menu, Close, CaretTop, CaretBottom } from '@element-plus/icons-vue'
import { fmtChange } from '@/utils/format'

defineProps<{
  visible: boolean
  sectorName: string
  loading: boolean
  stocks: any[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const router = useRouter()

function handleGoToStock(code: string) {
  router.push({ path: '/stock-detail', query: { code } })
  emit('update:visible', false)
}
</script>

<style scoped>
.sector-drawer :deep(.el-drawer__body) {
  padding: 0;
  display: flex;
  flex-direction: column;
}

.drawer-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-color);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-card);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  font-size: 18px;
  color: var(--el-color-primary);
}

.header-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
}

.count-tag {
  font-family: var(--font-mono);
  font-weight: 500;
}

.close-icon {
  font-size: 20px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.2s;
}

.close-icon:hover {
  color: var(--el-color-primary);
}

.drawer-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0;
  background: var(--bg-card);
}

.drawer-content :deep(.el-table) {
  flex: 1;
  min-height: 0;
  --el-table-border-color: var(--border-color-light);
  --el-table-header-bg-color: var(--bg-soft);
  --el-table-header-text-color: var(--text-muted);
}

.custom-table :deep(th.el-table__cell) {
  font-weight: 500;
  padding: 10px 0;
}

.custom-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.code-link {
  color: var(--el-color-primary);
  font-family: var(--font-mono);
  font-size: 13px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--el-color-primary-light-9);
  transition: all 0.2s;
}

.code-link:hover {
  background: var(--el-color-primary-light-8);
  text-decoration: none;
}

.change-cell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.money-text {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 2px;
}

.trend-icon {
  font-size: 14px;
}

.money-text.is-rise { color: var(--el-color-danger); }
.money-text.is-fall { color: var(--el-color-success); }
.text-muted { color: var(--text-muted); font-weight: normal; }
</style>