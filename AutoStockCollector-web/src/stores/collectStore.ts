import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { collectApi } from '@/api/collect'
import type { CollectProgress, TaskRecord } from '@/types'

export const useCollectStore = defineStore('collect', () => {
  const backendOnline = ref(false)
  const progressList = ref<CollectProgress[]>([])
  const tasks = ref<TaskRecord[]>([])
  const loading = ref(false)

  const completedCount = computed(() => {
    return progressList.value.filter(p => p.status === 'completed').length
  })

  const totalSuccessCount = computed(() => {
    return progressList.value.reduce((acc, p) => acc + (p.progress || 0), 0)
  })

  async function checkHealth() {
    try {
      await collectApi.getHealth()
      backendOnline.value = true
    } catch {
      backendOnline.value = false
    }
  }

  async function fetchProgress() {
    try {
      const res = await collectApi.getProgressAll()
      const body = res.data
      if (body?.tasks && typeof body.tasks === 'object') {
        // tasks 是 { kline: {...}, financial: {...}, ... } 对象
        progressList.value = Object.entries(body.tasks).map(([task_type, val]) => ({
          task_type,
          ...(val as object),
        } as CollectProgress))
      }
    } catch {
      // ignore
    }
  }

  async function fetchTasks(status?: string, limit = 50) {
    loading.value = true
    try {
      const res = await collectApi.getTasks({ status, limit })
      if (res.data) {
        tasks.value = res.data.data || res.data || []
      }
    } finally {
      loading.value = false
    }
  }

  return {
    backendOnline,
    progressList,
    tasks,
    loading,
    completedCount,
    totalSuccessCount,
    checkHealth,
    fetchProgress,
    fetchTasks,
  }
})

// AI analysis cache store
export const useAIStore = defineStore('ai', () => {
  const cache = ref<Record<string, unknown>>({})

  function getCached(key: string) {
    return cache.value[key]
  }

  function setCache(key: string, value: unknown) {
    cache.value[key] = value
  }

  return { cache, getCached, setCache }
})
