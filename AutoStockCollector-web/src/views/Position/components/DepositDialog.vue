<template>
  <el-dialog :model-value="visible" @update:model-value="$emit('update:visible', $event)" title="入金 / 出金" width="400px">
    <el-form label-width="100px">
      <el-form-item label="方向">
        <el-radio-group v-model="localDirection" size="small">
          <el-radio-button value="in">入金</el-radio-button>
          <el-radio-button value="out">出金</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="金额">
        <el-input-number v-model="localAmount" :min="0" :step="10000" style="width: 100%" />
      </el-form-item>
      <div class="dialog-hint">
        现金与初始资金会同步{{ localDirection === 'in' ? '增加' : '减少' }}，保留全部持仓与交易记录，总收益率口径不变。
      </div>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleConfirm">确认</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  visible: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'confirm', amount: number): void
}>()

const localDirection = ref<'in' | 'out'>('in')
const localAmount = ref(10000)

watch(() => props.visible, (val) => {
  if (val) {
    localDirection.value = 'in'
    localAmount.value = 10000
  }
})

function handleConfirm() {
  if (localAmount.value <= 0) {
    ElMessage.warning('金额必须大于 0')
    return
  }
  const signed = localDirection.value === 'in' ? localAmount.value : -localAmount.value
  emit('confirm', signed)
}
</script>

<style scoped>
.dialog-hint { margin-top: 16px; color: var(--text-muted); font-size: 13px; line-height: 1.5; padding: 8px 12px; background: var(--bg-body); border-radius: 4px; }
</style>