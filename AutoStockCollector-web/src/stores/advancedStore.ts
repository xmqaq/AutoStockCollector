import { defineStore } from 'pinia'
import { ref } from 'vue'
import { orchestrationApi } from '@/api/ai'

export const useAdvancedStore = defineStore('advanced', () => {
  const quickResult = ref<any>(null)
  const quickLoading = ref(false)
  const quickError = ref('')

  async function quickAnalyze(code: string) {
    quickLoading.value = true
    quickError.value = ''
    quickResult.value = null
    try {
      const res = await orchestrationApi.analyze({ code })
      quickResult.value = res.data?.data || res.data
    } catch (e: any) {
      quickError.value = e.message || '分析失败'
    } finally {
      quickLoading.value = false
    }
  }

  return {
    quickResult, quickLoading, quickError, quickAnalyze,
  }
})
