<template>
  <div class="todo-page">
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-num total">{{ todos.length }}</span>
        <span class="stat-lbl">总计</span>
      </div>
      <div class="stat-item">
        <span class="stat-num done">{{ doneCount }}</span>
        <span class="stat-lbl">已完成</span>
      </div>
      <div class="stat-item">
        <span class="stat-num pending">{{ pendingCount }}</span>
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
          {{ filteredTodos.length }} / {{ todos.length }}
        </el-tag>
      </div>

      <div v-if="filteredTodos.length === 0" class="empty-state">
        暂无{{ filter === 'all' ? '' : `「${filterLabels[filter]}」` }}事项
      </div>

      <div v-for="item in filteredTodos" :key="item.id" :class="['todo-item', { done: item.done }]">
        <el-checkbox :model-value="item.done" @change="toggleDone(item)" />
        <div class="todo-body" @click.stop="toggleDone(item)">
          <div class="todo-meta">
            <el-tag size="small" :type="tagType(item.category)">{{ filterLabels[item.category] }}</el-tag>
            <el-tag size="small" :type="item.done ? 'success' : 'warning'" effect="dark" style="border:0">
              {{ item.done ? '已完成' : '待完成' }}
            </el-tag>
            <span class="todo-time">{{ item.updatedAt || item.createdAt }}</span>
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
              ref="editInput"
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
import { ref, computed, onMounted, nextTick } from 'vue'

interface TodoItem {
  id: string
  text: string
  category: 'todo' | 'plan' | 'suggestion'
  done: boolean
  createdAt: string
  updatedAt: string
}

const STORAGE_KEY = 'opencode-todo-items'
const filterLabels: Record<string, string> = {
  todo: '待办事项',
  plan: '下一步计划',
  suggestion: '意见建议',
}

const todos = ref<TodoItem[]>([])
const filter = ref('all')
const showAdd = ref(false)
const newText = ref('')
const newCategory = ref<'todo' | 'plan' | 'suggestion'>('todo')
const editingId = ref<string | null>(null)
const editText = ref('')
const editCategory = ref<'todo' | 'plan' | 'suggestion'>('todo')
const editInput = ref<HTMLInputElement>()

const doneCount = computed(() => todos.value.filter(t => t.done).length)
const pendingCount = computed(() => todos.value.filter(t => !t.done).length)
const donePercent = computed(() => todos.value.length ? Math.round(doneCount.value / todos.value.length * 100) : 0)

const filteredTodos = computed(() => {
  if (filter.value === 'all') return todos.value
  return todos.value.filter(t => t.category === filter.value)
})

function tagType(cat: string) {
  switch (cat) {
    case 'todo': return 'warning'
    case 'plan': return 'primary'
    case 'suggestion': return 'success'
    default: return 'info'
  }
}

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) todos.value = JSON.parse(raw)
  } catch { todos.value = [] }
}

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos.value))
}

function addTodo() {
  const text = newText.value.trim()
  if (!text) return
  const now = new Date().toLocaleString('zh-CN')
  todos.value.unshift({
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    text,
    category: newCategory.value,
    done: false,
    createdAt: now,
    updatedAt: now,
  })
  save()
  newText.value = ''
  showAdd.value = false
}

function toggleDone(item: TodoItem) {
  item.done = !item.done
  item.updatedAt = new Date().toLocaleString('zh-CN')
  save()
}

function remove(id: string) {
  todos.value = todos.value.filter(t => t.id !== id)
  save()
}

function startEdit(item: TodoItem) {
  editingId.value = item.id
  editText.value = item.text
  editCategory.value = item.category
  nextTick(() => {
    const el = document.querySelector('.todo-edit-row .el-input__inner') as HTMLInputElement
    el?.focus()
  })
}

function confirmEdit() {
  if (!editingId.value) return
  const item = todos.value.find(t => t.id === editingId.value)
  if (item) {
    const text = editText.value.trim()
    if (text) item.text = text
    item.category = editCategory.value
    item.updatedAt = new Date().toLocaleString('zh-CN')
    save()
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
</style>
