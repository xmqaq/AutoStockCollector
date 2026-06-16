<template>
  <el-dialog 
    :model-value="visible" 
    @update:model-value="$emit('update:visible', $event)" 
    title="新增待办事项" 
    width="500px" 
    :close-on-click-modal="false"
    class="pro-dialog"
    destroy-on-close
  >
    <div class="dialog-content">
      <el-form label-position="top" require-asterisk-position="right">
        <el-form-item label="任务内容" required>
          <el-input
            v-model="formData.text"
            type="textarea"
            :rows="4"
            placeholder="请输入待办事项、下一步计划或意见建议... (支持 Ctrl+Enter 快捷提交)"
            @keyup.enter.ctrl="handleAdd"
            resize="none"
            class="custom-textarea"
          />
        </el-form-item>
        <el-form-item label="任务分类" required>
          <el-radio-group v-model="formData.category" class="category-group">
            <el-radio-button label="todo">
              <el-icon><Timer /></el-icon> 待办事项
            </el-radio-button>
            <el-radio-button label="plan">
              <el-icon><Calendar /></el-icon> 下一步计划
            </el-radio-button>
            <el-radio-button label="suggestion">
              <el-icon><ChatLineSquare /></el-icon> 意见建议
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="$emit('update:visible', false)" class="cancel-btn">取消</el-button>
        <el-button 
          type="primary" 
          :disabled="!formData.text.trim()" 
          @click="handleAdd" 
          :loading="loading"
          class="submit-btn"
        >
          确认添加
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import { Timer, Calendar, ChatLineSquare } from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'add', payload: { text: string; category: 'todo' | 'plan' | 'suggestion' }): void
}>()

const formData = reactive({
  text: '',
  category: 'todo' as 'todo' | 'plan' | 'suggestion'
})

// 每次打开弹窗时重置表单
watch(() => props.visible, (val) => {
  if (val) {
    formData.text = ''
    formData.category = 'todo'
  }
})

function handleAdd() {
  if (!formData.text.trim()) return
  emit('add', { text: formData.text.trim(), category: formData.category })
}
</script>

<style scoped>
.pro-dialog :deep(.el-dialog__header) {
  margin-right: 0;
  padding: 20px 24px;
  border-bottom: 1px solid #ebeef5;
}

.pro-dialog :deep(.el-dialog__title) {
  font-weight: 600;
  font-size: 18px;
  color: #303133;
}

.pro-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.pro-dialog :deep(.el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid #ebeef5;
}

.dialog-content :deep(.el-form-item__label) {
  font-weight: 500;
  color: #303133;
  padding-bottom: 8px;
}

.custom-textarea :deep(.el-textarea__inner) {
  border-radius: 8px;
  padding: 12px;
  background-color: #f5f7fa;
  border: 1px solid transparent;
  transition: all 0.3s;
}

.custom-textarea :deep(.el-textarea__inner:focus) {
  background-color: #ffffff;
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-5);
}

.category-group {
  display: flex;
  width: 100%;
}

.category-group :deep(.el-radio-button) {
  flex: 1;
}

.category-group :deep(.el-radio-button__inner) {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.cancel-btn, .submit-btn {
  padding: 10px 24px;
  border-radius: 6px;
  font-weight: 500;
}
</style>
