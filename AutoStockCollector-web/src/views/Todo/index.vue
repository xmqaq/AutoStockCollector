<template>
  <div class="todo-page">
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-num total">{{ globalStats.total }}</span>
        <span class="stat-lbl">总计</span>
      </div>
      <div class="stat-item">
        <span class="stat-num done">{{ globalStats.done }}</span>
        <span class="stat-lbl">已完成</span>
      </div>
      <div class="stat-item">
        <span class="stat-num pending">{{ globalStats.pending }}</span>
        <span class="stat-lbl">待完成</span>
      </div>
      <el-progress
        :percentage="donePercent"
        :stroke-width="10"
        class="stat-progress"
        :color="donePercent === 100 ? '#67c23a' : '#409eff'"
      />
    </div>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span>待办事项</span>
          <el-button type="primary" size="small" @click="showAdd = true">新增</el-button>
        </div>
      </template>

      <div class="filter-bar">
        <el-select v-model="filter" size="small" style="width: 140px">
          <el-option label="全部" value="all" />
          <el-option label="待办事项" value="todo" />
          <el-option label="下一步计划" value="plan" />
          <el-option label="意见建议" value="suggestion" />
        </el-select>
        <el-tag type="info" size="small">
          {{ pagination.total }} / {{ globalStats.total }}
        </el-tag>
      </div>

      <div v-if="items.length === 0" class="empty-state">
        暂无{{ filter === 'all' ? '' : `「${filterLabels[filter]}」` }}事项
      </div>

      <div v-for="item in items" :key="item.id" :class="['todo-item', { done: item.done }]">
        <el-checkbox :model-value="item.done" @change="toggleDone(item)" />
        <div class="todo-body" @click.stop="toggleDone(item)">
          <div class="todo-meta">
            <el-tag size="small" :type="tagType(item.category)">{{ filterLabels[item.category] }}</el-tag>
            <el-tag size="small" :type="item.done ? 'success' : 'warning'" effect="dark" style="border:0">
              {{ item.done ? '已完成' : '待完成' }}
            </el-tag>
            <span class="todo-time">
              <template v-if="item.submitterIp">{{ item.submitterIp }} · </template>{{ item.updatedAt || item.createdAt }}
            </span>
          </div>
          <div
            v-if="editingId !== item.id"
            class="todo-text"
            :class="{ 'line-through': item.done }"
            @dblclick.stop="startEdit(item)"
          >
            {{ item.text }}
          </div>
          <div v-else class="todo-edit-row">
            <el-input
              :ref="(el: any) => el && setEditRef(item.id, el)"
              v-model="editText"
              size="small"
              @keyup.enter="confirmEdit"
              @keyup.escape="cancelEdit"
              @blur="confirmEdit"
            />
            <el-select v-model="editCategory" size="small" style="width: 120px" @change="confirmEdit">
              <el-option label="待办事项" value="todo" />
              <el-option label="下一步计划" value="plan" />
              <el-option label="意见建议" value="suggestion" />
            </el-select>
          </div>
        </div>
        <el-button text size="small" type="danger" @click="remove(item.id)">删除</el-button>
      </div>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @change="load"
        />
      </div>
    </el-card>

    <el-dialog v-model="showAdd" title="新增事项" width="480px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="内容">
          <el-input
            v-model="newText"
            type="textarea"
            :rows="3"
            placeholder="输入待办事项、下一步计划或意见建议..."
            @keyup.enter.ctrl="addTodo"
          />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="newCategory" style="width: 100%">
            <el-option label="待办事项" value="todo" />
            <el-option label="下一步计划" value="plan" />
            <el-option label="意见建议" value="suggestion" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" :disabled="!newText.trim()" @click="addTodo">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { todoApi, type TodoItem } from '@/api/todo'

const filterLabels: Record<string, string> = {
  todo: '待办事项',
  plan: '下一步计划',
  suggestion: '意见建议',
}

const items = ref<TodoItem[]>([])
const filter = ref('all')
const showAdd = ref(false)
const newText = ref('')
const newCategory = ref<'todo' | 'plan' | 'suggestion'>('todo')
const editingId = ref<string | null>(null)
const editText = ref('')
const editCategory = ref<'todo' | 'plan' | 'suggestion'>('todo')

const editInputMap = new Map<string, any>()
function setEditRef(id: string, el: any) {
  editInputMap.set(id, el)
}

const pagination = ref({ page: 1, pageSize: 20, total: 0 })
const globalStats = ref({ total: 0, done: 0, pending: 0 })

const donePercent = computed(() =>
  globalStats.value.total
    ? Math.round((globalStats.value.done / globalStats.value.total) * 100)
    : 0
)

function tagType(cat: string) {
  switch (cat) {
    case 'todo': return 'warning'
    case 'plan': return 'primary'
    case 'suggestion': return 'success'
    default: return 'info'
  }
}

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

async function addTodo() {
  const text = newText.value.trim()
  if (!text) return
  try {
    await todoApi.create({ text, category: newCategory.value })
    newText.value = ''
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

async function remove(id: string) {
  try {
    await todoApi.remove(id)
    await load()
  } catch {
    ElMessage.error('删除失败，请稍后重试')
  }
}

function startEdit(item: TodoItem) {
  editingId.value = item.id
  editText.value = item.text
  editCategory.value = item.category
  nextTick(() => {
    const inputComp = editInputMap.get(item.id)
    inputComp?.focus?.() ?? inputComp?.input?.focus?.()
  })
}

async function confirmEdit() {
  if (!editingId.value) return
  const item = items.value.find(t => t.id === editingId.value)
  if (item) {
    const text = editText.value.trim()
    const updates: Partial<Pick<TodoItem, 'text' | 'category'>> = { category: editCategory.value }
    if (text) updates.text = text
    try {
      await todoApi.update(item.id, updates)
      await load()
    } catch {
      ElMessage.error('保存失败，请稍后重试')
    }
  }
  editingId.value = null
}

function cancelEdit() {
  editingId.value = null
}

onMounted(load)
</script>

<style scoped>
.todo-page {
  padding: 16px;
}

.stats-bar {
  display: flex;
  align-items: center;
  gap: 24px;
  background: #1f1f1f;
  border: 1px solid #2c2c2c;
  border-radius: 6px;
  padding: 14px 20px;
  margin-bottom: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 56px;
}

.stat-num {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-num.total { color: #e5eaf3; }
.stat-num.done { color: #67c23a; }
.stat-num.pending { color: #e6a23c; }

.stat-lbl {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.stat-progress {
  flex: 1;
  max-width: 300px;
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

.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.empty-state {
  text-align: center;
  color: #4a4a4a;
  padding: 40px 0;
  font-size: 14px;
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid transparent;
  margin-bottom: 6px;
  transition: all 0.2s;
  background: #2c2c2c;
}

.todo-item:hover {
  border-color: #3c3c3c;
}

.todo-item.done {
  opacity: 0.55;
}

.todo-body {
  flex: 1;
  min-width: 0;
}

.todo-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.todo-time {
  font-size: 11px;
  color: #606266;
}

.todo-text {
  font-size: 13px;
  color: #e5eaf3;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  cursor: pointer;
}

.todo-text:hover {
  color: #409eff;
}

.todo-text.line-through {
  text-decoration: line-through;
  color: #606266;
}

.todo-edit-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.todo-edit-row :deep(.el-input__wrapper) {
  background: #1a1a1a;
  box-shadow: 0 0 0 1px #3c3c3c inset;
}

.todo-edit-row :deep(.el-select .el-input__wrapper) {
  background: #1a1a1a;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid #2c2c2c;
  margin-top: 8px;
}

.pagination-bar :deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-button-bg-color: #2c2c2c;
  --el-pagination-hover-color: #409eff;
}
</style>
