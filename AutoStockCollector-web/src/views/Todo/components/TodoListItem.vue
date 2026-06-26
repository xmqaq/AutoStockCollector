<template>
  <div :class="['todo-item-card', { 'is-done': item.done }]">
    <div class="todo-checkbox">
      <el-checkbox :model-value="item.done" size="large" @change="$emit('toggle', item)" />
    </div>
    
    <div class="todo-content" @click.stop="$emit('toggle', item)">
      <div class="todo-header">
        <div class="todo-tags">
          <el-tag size="small" :type="tagType(item.category)" effect="light" round>
            {{ filterLabels[item.category] }}
          </el-tag>
          <el-tag v-if="item.done" size="small" type="success" effect="plain" round>
            <el-icon><Check /></el-icon> 已完成
          </el-tag>
          <el-tag v-else size="small" type="warning" effect="plain" round>
            <el-icon><Timer /></el-icon> 待完成
          </el-tag>
        </div>
        <div class="todo-time">
          <el-icon><User /></el-icon>
          <template v-if="item.submitterName">{{ item.submitterName }}</template>
          <template v-else-if="item.submitterIp">{{ item.submitterIp }}</template>
          <template v-else>匿名</template>
          <span class="time-divider">·</span>
          {{ item.updatedAt || item.createdAt }}
        </div>
      </div>
      
      <div
        v-if="!isEditing"
        class="todo-text"
        :class="{ 'line-through': item.done }"
        @dblclick.stop="startEdit"
      >
        {{ item.text }}
      </div>
      
      <div v-else class="todo-edit-area" @click.stop>
        <el-input
          ref="editInputRef"
          v-model="editForm.text"
          type="textarea"
          autosize
          placeholder="编辑待办事项内容"
          @keyup.enter.ctrl="confirmEdit"
          @keyup.escape="cancelEdit"
        />
        <div class="edit-actions">
          <el-select v-model="editForm.category" size="small" style="width: 120px">
            <el-option label="待办事项" value="todo" />
            <el-option label="下一步计划" value="plan" />
            <el-option label="意见建议" value="suggestion" />
          </el-select>
          <div class="action-buttons">
            <el-button size="small" @click="cancelEdit">取消</el-button>
            <el-button type="primary" size="small" @click="confirmEdit">保存</el-button>
          </div>
        </div>
      </div>
    </div>
    
    <div class="todo-actions">
      <el-tooltip content="双击内容进行编辑" placement="top" :show-after="500">
        <el-button circle plain size="small" @click.stop="startEdit">
          <el-icon><Edit /></el-icon>
        </el-button>
      </el-tooltip>
      <el-popconfirm
        title="确认删除此事项？"
        confirm-button-text="删除"
        confirm-button-type="danger"
        cancel-button-text="取消"
        @confirm="$emit('remove', item.id)"
      >
        <template #reference>
          <el-button type="danger" circle plain size="small" @click.stop>
            <el-icon><Delete /></el-icon>
          </el-button>
        </template>
      </el-popconfirm>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue'
import { Check, Timer, User, Edit, Delete } from '@element-plus/icons-vue'
import type { TodoItem } from '@/api/todo'

const props = defineProps<{
  item: TodoItem
  filterLabels: Record<string, string>
}>()

const emit = defineEmits<{
  (e: 'toggle', item: TodoItem): void
  (e: 'remove', id: string): void
  (e: 'update', id: string, updates: Partial<Pick<TodoItem, 'text' | 'category'>>): void
}>()

const isEditing = ref(false)
const editInputRef = ref<any>(null)

const editForm = reactive({
  text: '',
  category: 'todo' as 'todo' | 'plan' | 'suggestion'
})

function tagType(cat: string) {
  switch (cat) {
    case 'todo': return 'warning'
    case 'plan': return 'primary'
    case 'suggestion': return 'success'
    default: return 'info'
  }
}

function startEdit() {
  isEditing.value = true
  editForm.text = props.item.text
  editForm.category = props.item.category
  
  nextTick(() => {
    editInputRef.value?.focus?.() ?? editInputRef.value?.input?.focus?.()
  })
}

function confirmEdit() {
  if (!isEditing.value) return
  
  const text = editForm.text.trim()
  const updates: Partial<Pick<TodoItem, 'text' | 'category'>> = { category: editForm.category }
  
  if (text && (text !== props.item.text || editForm.category !== props.item.category)) {
    updates.text = text
    emit('update', props.item.id, updates)
  }
  
  isEditing.value = false
}

function cancelEdit() {
  isEditing.value = false
}
</script>

<style scoped>
.todo-item-card {
  display: flex;
  align-items: flex-start;
  padding: 16px 20px;
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  margin-bottom: 12px;
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  position: relative;
  overflow: hidden;
}

.todo-item-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

.todo-item-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background-color: transparent;
  transition: background-color 0.3s;
}

.todo-item-card:hover::before {
  background-color: var(--el-color-primary);
}

.todo-item-card.is-done {
  background-color: var(--bg-soft);
  border-color: #f0f2f5;
  opacity: 0.8;
}

.todo-item-card.is-done::before {
  background-color: var(--el-color-success);
}

.todo-checkbox {
  margin-top: 2px;
  margin-right: 16px;
}

.todo-checkbox :deep(.el-checkbox__inner) {
  width: 20px;
  height: 20px;
  border-radius: 6px;
}

.todo-checkbox :deep(.el-checkbox__inner::after) {
  height: 10px;
  left: 6px;
  width: 4px;
}

.todo-content {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}

.todo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.todo-tags {
  display: flex;
  gap: 8px;
  align-items: center;
}

.todo-tags :deep(.el-tag) {
  border-radius: 12px;
  padding: 0 10px;
  height: 22px;
  line-height: 20px;
}

.todo-time {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

.time-divider {
  margin: 0 4px;
  color: #dcdfe6;
}

.todo-text {
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  transition: color 0.3s;
}

.todo-text.line-through {
  text-decoration: line-through;
  color: var(--text-muted);
}

.todo-edit-area {
  margin-top: 4px;
  background: var(--bg-soft);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  cursor: default;
}

.edit-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.todo-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-left: 16px;
  opacity: 0;
  transform: translateX(10px);
  transition: all 0.3s ease;
}

.todo-item-card:hover .todo-actions {
  opacity: 1;
  transform: translateX(0);
}
</style>
