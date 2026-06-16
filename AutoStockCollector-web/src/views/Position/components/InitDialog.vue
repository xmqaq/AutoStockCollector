<template>
  <el-dialog :model-value="visible" @update:model-value="$emit('update:visible', $event)" title="初始化模拟账户" width="400px">
    <el-form label-width="100px">
      <el-form-item label="初始资金">
        <el-input-number v-model="localCapital" :min="1000" :step="10000" style="width: 100%" />
      </el-form-item>
      <div class="dialog-warn">注意：初始化将清空所有交易记录和持仓！</div>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleConfirm">确认初始化</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { formatAmount } from '../utils'

const props = defineProps<{
  visible: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'confirm', capital: number): void
}>()

const localCapital = ref(100000)

watch(() => props.visible, (val) => {
  if (val) localCapital.value = 100000
})

async function handleConfirm() {
  if (localCapital.value <= 0) return
  try {
    await ElMessageBox.confirm(
      `确认将模拟账户初始资金设为 ${formatAmount(localCapital.value)}？所有持仓和交易记录将被清空！`,
      '初始化确认',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  emit('confirm', localCapital.value)
}
</script>

<style scoped>
.dialog-warn { margin-top: 16px; color: var(--el-color-danger); font-size: 13px; padding: 8px 12px; background: var(--el-color-danger-light-9); border-radius: 4px; }
</style>