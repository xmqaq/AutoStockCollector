<template>
  <el-input
    v-model="inputValue"
    :placeholder="placeholder"
    clearable
    @keyup.enter="handleSearch"
    @clear="handleClear"
    class="stock-search"
  >
    <template #append>
      <el-button @click="handleSearch" :icon="Search">搜索</el-button>
    </template>
  </el-input>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { normalizeCode } from '@/utils/stockCode'
import { ElMessage } from 'element-plus'

interface Props {
  modelValue?: string
  placeholder?: string
  autoNormalize?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  placeholder: '输入股票代码，如 600000 或 SH600000',
  autoNormalize: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  search: [code: string]
}>()

const inputValue = ref(props.modelValue)

watch(() => props.modelValue, (val) => {
  inputValue.value = val
})

function handleSearch() {
  let code = inputValue.value.trim()
  if (!code) {
    ElMessage.warning('请输入股票代码')
    return
  }
  if (props.autoNormalize) {
    code = normalizeCode(code)
  }
  emit('update:modelValue', code)
  emit('search', code)
}

function handleClear() {
  emit('update:modelValue', '')
  emit('search', '')
}
</script>

<style scoped>
.stock-search {
  width: 100%;
  max-width: 400px;
}
</style>
