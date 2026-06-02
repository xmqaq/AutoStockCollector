import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { collectApi } from '@/api/collect'
import type { CollectProgress, TaskRecord } from '@/types'

export const useCollectStore = defineStore('collect', () => {
  const backendOnline = ref(false)
  const progressList = ref<CollectProgress[]>([])
  const tasks = ref<TaskRecord[]>([])
  const loading = ref(false)
  const overallPercent = ref(0)

  // 已有数据（含 not_started 但 DB 有记录）都算完成
  const completedCount = computed(() => {
    return progressList.value.filter(p =>
      p.status === 'completed' ||
      (p.status === 'not_started' && (p.record_count || 0) > 0)
    ).length
  })

  const totalSuccessCount = computed(() => {
    // 优先累加各集合实际记录数（DB中的数据量）
    const dbTotal = progressList.value.reduce((acc, p) => acc + (p.record_count || 0), 0)
    if (dbTotal > 0) return dbTotal
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
        const entries = Object.entries(body.tasks)
        // 只有后端返回了有效数据时才更新，防止瞬时空数据覆盖已有正确数据
        if (entries.length > 0) {
          progressList.value = entries.map(([task_type, val]) => ({
            task_type,
            ...(val as object),
          } as CollectProgress))
        }
      }
      if (typeof body?.overall_percent === 'number') {
        overallPercent.value = Math.round(body.overall_percent)
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
        const raw: TaskRecord[] = res.data.tasks || res.data.data || []
        raw.sort((a, b) => {
          if (a.status === 'running' && b.status !== 'running') return -1
          if (a.status !== 'running' && b.status === 'running') return 1
          const ta = a.create_time || a.created_at || ''
          const tb = b.create_time || b.created_at || ''
          return tb > ta ? 1 : tb < ta ? -1 : 0
        })
        tasks.value = raw
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
    overallPercent,
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
