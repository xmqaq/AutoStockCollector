import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { orchestrationApi, type FinalVerdict } from '@/api/ai'

export interface GraphNodeState {
  node_id: string
  name: string
  status: 'idle' | 'running' | 'completed' | 'error'
  content: string
}

export const useOrchestrationStore = defineStore('orchestration', () => {
  const stockCode = ref('')
  const isAnalyzing = ref(false)
  const error = ref('')
  const runId = ref('')
  const verdict = ref<FinalVerdict | null>(null)
  const nodes = ref<GraphNodeState[]>([])
  const events = ref<any[]>([])
  const overallProgress = ref(0)

  const activeNodes = computed(() => nodes.value.filter(n => n.status === 'running'))
  const completedNodes = computed(() => nodes.value.filter(n => n.status === 'completed'))
  const isAllCompleted = computed(() => verdict.value !== null)

  const executionOrder = [
    'data_fetch', 'factor_calc',
    'analyst_market_analyst', 'analyst_technical_analyst', 'analyst_fund_analyst',
    'analyst_fundamental_analyst', 'analyst_sentiment_analyst', 'analyst_risk_analyst',
    'bull_analyst', 'bear_analyst',
    'research_manager', 'trader',
    'risk_aggressive', 'risk_conservative', 'risk_neutral',
    'portfolio_manager',
  ]

  function reset() {
    stockCode.value = ''
    isAnalyzing.value = false
    error.value = ''
    runId.value = ''
    verdict.value = null
    nodes.value = []
    events.value = []
    overallProgress.value = 0
  }

  function handleGraphEvent(event: string, data: any) {
    events.value.push({ event, data })
    let nodeId = ''
    let nodeName = ''

    if (data?.node_id) {
      nodeId = data.node_id
      nodeName = data.name || data.node_id
    }

    switch (event) {
      case 'graph:node_start':
        const idx = nodes.value.findIndex(n => n.node_id === nodeId)
        if (idx >= 0) {
          nodes.value[idx].status = 'running'
        } else {
          nodes.value.push({ node_id: nodeId, name: nodeName, status: 'running', content: '' })
        }
        updateProgress()
        break

      case 'graph:node_stream':
        {
          const n = nodes.value.find(n => n.node_id === nodeId)
          if (n) n.content += (data?.content || '')
        }
        break

      case 'graph:node_complete':
        {
          const n = nodes.value.find(n => n.node_id === nodeId)
          if (n) n.status = 'completed'
        }
        updateProgress()
        break

      case 'graph:complete':
        verdict.value = data?.verdict || data?.final_output || null
        isAnalyzing.value = false
        updateProgress()
        break

      case 'error':
        error.value = data || 'Unknown error'
        isAnalyzing.value = false
        break
    }
  }

  function updateProgress() {
    const total = executionOrder.length
    const done = nodes.value.filter(n =>
      n.status === 'completed' || n.status === 'error'
    ).length
    overallProgress.value = total > 0 ? Math.round((done / total) * 100) : 0
  }

  async function startAnalysis(code: string) {
    reset()
    stockCode.value = code
    isAnalyzing.value = true
    let timeoutId: ReturnType<typeof setTimeout> | null = null

    try {
      const response = await orchestrationApi.analyzeStream({ code })
      if (!response.ok || !response.body) {
        error.value = '无法连接分析服务'
        isAnalyzing.value = false
        return
      }

      timeoutId = setTimeout(() => {
        if (isAnalyzing.value) {
          error.value = '分析超时（60秒无响应）'
          isAnalyzing.value = false
        }
      }, 60000)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        if (timeoutId) {
          clearTimeout(timeoutId)
          timeoutId = null
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const parsed = JSON.parse(line.slice(6))
            handleGraphEvent(parsed.event || parsed.type, parsed.data)
          } catch { /* skip malformed */ }
        }
      }
    } catch (err: any) {
      error.value = err.message || '分析流中断'
    } finally {
      if (timeoutId) clearTimeout(timeoutId)
      isAnalyzing.value = false
    }
  }

  return {
    stockCode,
    isAnalyzing,
    error,
    runId,
    verdict,
    nodes,
    events,
    overallProgress,
    activeNodes,
    completedNodes,
    isAllCompleted,
    reset,
    startAnalysis,
    handleGraphEvent,
  }
})
