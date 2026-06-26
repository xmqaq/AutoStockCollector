<template>
  <div class="todo-page">
    <div class="page-header">
      <h2 class="page-title">待办事项管理</h2>
      <p class="page-desc">高效管理您的任务、计划与意见建议</p>
    </div>

    <TodoStats :stats="globalStats" />

    <el-card shadow="never" class="pro-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">任务列表</span>
          <el-button type="primary" size="default" @click="showAdd = true">
            <el-icon class="el-icon--left"><Plus /></el-icon>新增事项
          </el-button>
        </div>
      </template>

      <div class="filter-bar">
        <el-radio-group v-model="filter" size="default" class="filter-group">
          <el-radio-button label="all">全部任务</el-radio-button>
          <el-radio-button label="todo">待办事项</el-radio-button>
          <el-radio-button label="plan">下一步计划</el-radio-button>
          <el-radio-button label="suggestion">意见建议</el-radio-button>
        </el-radio-group>
        <div class="filter-stats">
          当前展示：<span class="highlight">{{ pagination.total }}</span> / 总计：<span>{{ globalStats.total }}</span>
        </div>
      </div>

      <div v-if="items.length === 0" class="empty-state">
        <el-empty 
          :description="`暂无${filter === 'all' ? '任何' : '「' + filterLabels[filter] + '」'}事项`" 
          :image-size="120" 
        />
      </div>

      <div class="todo-list-wrapper" v-else>
        <TodoListItem
          v-for="item in items"
          :key="item.id"
          :item="item"
          :filter-labels="filterLabels"
          @toggle="toggleDone"
          @remove="remove"
          @update="updateItem"
        />
      </div>

      <div class="pagination-bar" v-if="items.length > 0 || pagination.total > 0">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @change="load"
        />
      </div>
    </el-card>

    <TodoAddDialog
      v-model:visible="showAdd"
      @add="addTodo"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { todoApi, type TodoItem } from '@/api/todo'

import TodoStats from './components/TodoStats.vue'
import TodoListItem from './components/TodoListItem.vue'
import TodoAddDialog from './components/TodoAddDialog.vue'

const filterLabels: Record<string, string> = {
  todo: '待办事项',
  plan: '下一步计划',
  suggestion: '意见建议',
}

const items = ref<TodoItem[]>([])
const filter = ref('all')
const showAdd = ref(false)

const pagination = ref({ page: 1, pageSize: 20, total: 0 })
const globalStats = ref({ total: 0, done: 0, pending: 0 })

async function load() {
  try {
    const res = await todoApi.list({
      page: pagination.value.page,
      pageSize: pagination.value.pageSize,
      category: filter.value as 'todo' | 'plan' | 'suggestion' | 'all',
    })
    const payload = res.data
    items.value = payload.data
    pagination.value.total = payload.pagination.total
    globalStats.value = payload.stats
  } catch {
    ElMessage.error('加载失败，请稍后重试')
  }
}

watch(filter, () => {
  pagination.value.page = 1
  load()
})

async function addTodo(payload: { text: string; category: 'todo' | 'plan' | 'suggestion' }) {
  try {
    await todoApi.create(payload)
    showAdd.value = false
    pagination.value.page = 1
    await load()
  } catch {
    ElMessage.error('添加失败，请稍后重试')
  }
}

async function toggleDone(item: TodoItem) {
  try {
    await todoApi.update(item.id, { done: !item.done })
    await load()
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  }
}

async function updateItem(id: string, updates: Partial<Pick<TodoItem, 'text' | 'category'>>) {
  try {
    await todoApi.update(id, updates)
    await load()
  } catch {
    ElMessage.error('保存失败，请稍后重试')
  }
}

async function remove(id: string) {
  try {
    await todoApi.remove(id)
    if (items.value.length === 1 && pagination.value.page > 1) {
      pagination.value.page -= 1
    }
    await load()
  } catch {
    ElMessage.error('删除失败，请稍后重试')
  }
}

onMounted(load)
</script>

<style scoped>
.todo-page {
  padding: 24px;
  background-color: var(--bg-soft);
  height: 100%; /* 根据实际头部高度调整 */
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-desc {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
}

.pro-card {
  border: none;
  border-radius: 12px;
  box-shadow: 0 4px 16px var(--bg-hover-subtle);
  background: var(--bg-card);
}

.pro-card :deep(.el-card__header) {
  border-bottom: 1px solid #ebeef5;
  padding: 18px 24px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
}

.card-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: var(--el-color-primary);
  border-radius: 2px;
  margin-right: 8px;
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding: 0 4px;
}

.filter-group :deep(.el-radio-button__inner) {
  padding: 10px 20px;
  font-weight: 500;
}

.filter-stats {
  font-size: 14px;
  color: var(--text-secondary);
}

.filter-stats .highlight {
  color: var(--el-color-primary);
  font-weight: 600;
  font-size: 16px;
}

.empty-state {
  padding: 60px 0;
}

.todo-list-wrapper {
  min-height: 200px;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding-top: 20px;
  margin-top: 20px;
  border-top: 1px dashed #ebeef5;
}

.pagination-bar :deep(.el-pagination.is-background .el-pager li:not(.is-disabled).is-active) {
  background-color: var(--el-color-primary);
  color: #fff;
  font-weight: 600;
}
</style>
