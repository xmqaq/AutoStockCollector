import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { debateApi, type FinalVerdict } from '@/api/ai'

export interface StreamDebateState {
  status: 'idle' | 'running' | 'completed' | 'error'
  progress: number
  content: string
  score?: number
  error?: string
}

export interface BaseAgentState {
  agent_id: string
  name: string
  status: 'idle' | 'running' | 'completed' | 'error'
  content: string
}

export interface DataSourceState {
  name: string
  label: string
  status: 'waiting' | 'running' | 'done' | 'error'
}

export interface FactorState {
  name: string
  label: string
  status: 'waiting' | 'running' | 'done' | 'error'
  score: number
}

export const useDebateStore = defineStore('debate', () => {
  const stockCode = ref('')
  const isAnalyzing = ref(false)
  const error = ref('')

  const bull = ref<StreamDebateState>({ status: 'idle', progress: 0, content: '' })
  const bear = ref<StreamDebateState>({ status: 'idle', progress: 0, content: '' })
  const judge = ref<StreamDebateState>({ status: 'idle', progress: 0, content: '' })
  const verdict = ref<FinalVerdict | null>(null)

  const baseAgents = ref<BaseAgentState[]>([])
  const isBasePhase = ref(false)

  const dataSources = ref<DataSourceState[]>([])
  const isDataPhase = ref(false)
  const factorItems = ref<FactorState[]>([])
  const isFactorPhase = ref(false)
  const factorResults = ref<any>(null)

  const bullContent = computed(() => bull.value.content)
  const bearContent = computed(() => bear.value.content)
  const judgeContent = computed(() => judge.value.content)

  const isBullCompleted = computed(() => bull.value.status === 'completed')
  const isBearCompleted = computed(() => bear.value.status === 'completed')
  const isJudgeCompleted = computed(() => judge.value.status === 'completed')
  const isAllCompleted = computed(() => verdict.value !== null)

  const baseCompletedCount = computed(() =>
    baseAgents.value.filter(a => a.status === 'completed').length
  )
  const baseTotal = computed(() => baseAgents.value.length)

  const overallProgress = computed(() => {
    if (verdict.value) return 100
    if (isDataPhase.value) return 5
    if (isFactorPhase.value) return 10
    if (isBasePhase.value && baseTotal.value > 0) {
      return 15 + Math.round((baseCompletedCount.value / baseTotal.value) * 35)
    }
    const total = bull.value.progress + bear.value.progress + judge.value.progress
    return Math.round(total / 3 * 0.5 + 50) || 0
  })

  const phase = computed(() => {
    if (verdict.value) return 'verdict'
    if (judge.value.status === 'running' || judge.value.status === 'completed') return 'judge'
    if (bear.value.status === 'running' || bear.value.status === 'completed') return 'bear'
    if (bull.value.status === 'running' || bull.value.status === 'completed') return 'bull'
    if (isBasePhase.value) return 'base'
    if (isFactorPhase.value) return 'factor'
    if (isDataPhase.value) return 'data'
    return 'idle'
  })

  function reset() {
    stockCode.value = ''
    isAnalyzing.value = false
    error.value = ''
    bull.value = { status: 'idle', progress: 0, content: '' }
    bear.value = { status: 'idle', progress: 0, content: '' }
    judge.value = { status: 'idle', progress: 0, content: '' }
    verdict.value = null
    baseAgents.value = []
    isBasePhase.value = false
    dataSources.value = []
    isDataPhase.value = false
    factorItems.value = []
    isFactorPhase.value = false
    factorResults.value = null
  }

  async function startDebate(code: string) {
    reset()
    stockCode.value = code
    isAnalyzing.value = true

    try {
      const response = await debateApi.stream({ code })
      if (!response.ok || !response.body) {
        error.value = '无法连接辩论服务'
        isAnalyzing.value = false
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const parsed = JSON.parse(line.slice(6))
            handleEvent(parsed)
            await new Promise(r => setTimeout(r, 0))
          } catch {
            // skip malformed events
          }
        }
      }
    } catch (err: any) {
      error.value = err.message || '辩论流中断'
    } finally {
      isAnalyzing.value = false
    }
  }

  function handleEvent(parsed: any) {
    const event = parsed.event
    const data = parsed.data

    switch (event) {
      case 'data:start':
        isDataPhase.value = true
        dataSources.value = [
          { name: 'kline', label: 'K线行情', status: 'waiting' },
          { name: 'stock_info', label: '基本资料', status: 'waiting' },
          { name: 'fund_flow', label: '资金流向', status: 'waiting' },
          { name: 'news', label: '新闻舆情', status: 'waiting' },
          { name: 'financial', label: '财务数据', status: 'waiting' },
          { name: 'margin', label: '融资融券', status: 'waiting' },
        ]
        break

      case 'data:progress':
        {
          const ds = dataSources.value.find(d => d.name === parsed.name)
          if (ds) ds.status = parsed.status || 'done'
        }
        break

      case 'data:done':
        isDataPhase.value = false
        break

      case 'factor:start':
        isFactorPhase.value = true
        factorItems.value = [
          { name: 'technical', label: '技术面因子', status: 'waiting', score: 0 },
          { name: 'fundamental', label: '基本面因子', status: 'waiting', score: 0 },
          { name: 'fund_flow', label: '资金面因子', status: 'waiting', score: 0 },
          { name: 'valuation', label: '估值因子', status: 'waiting', score: 0 },
        ]
        break

      case 'factor:progress':
        {
          const fi = factorItems.value.find(f => f.name === parsed.name)
          if (fi) {
            fi.status = parsed.status || 'done'
            if (parsed.score != null) fi.score = parsed.score
          }
        }
        break

      case 'factor:done':
        isFactorPhase.value = false
        factorResults.value = data
        break

      case 'base:start':
        isBasePhase.value = true
        break

      case 'agent:start':
        baseAgents.value.push({
          agent_id: parsed.agent_id,
          name: parsed.name || parsed.agent_id,
          status: 'running',
          content: '',
        })
        break

      case 'agent:content':
        {
          const agent = baseAgents.value.find(a => a.agent_id === parsed.agent_id)
          if (agent) {
            agent.content += data || ''
          }
        }
        break

      case 'agent:done':
        {
          const agent = baseAgents.value.find(a => a.agent_id === parsed.agent_id)
          if (agent) agent.status = 'completed'
        }
        break

      case 'base:done':
        isBasePhase.value = false
        break

      case 'progress':
        if (parsed.agent === 'bull') bull.value.progress = parsed.progress
        else if (parsed.agent === 'bear') bear.value.progress = parsed.progress
        else if (parsed.agent === 'judge') judge.value.progress = parsed.progress
        break

      case 'bull:start':
        bull.value = { status: 'running', progress: 20, content: '' }
        break
      case 'bull:content':
        bull.value.content += data || ''
        break
      case 'bull:done':
        bull.value = { status: 'completed', progress: 100, content: bull.value.content, score: parsed.score }
        break
      case 'bull:error':
        bull.value = { status: 'error', progress: 0, content: '', error: data }
        break

      case 'bear:start':
        bear.value = { status: 'running', progress: 50, content: '' }
        break
      case 'bear:content':
        bear.value.content += data || ''
        break
      case 'bear:done':
        bear.value = { status: 'completed', progress: 100, content: bear.value.content, score: parsed.score }
        break
      case 'bear:error':
        bear.value = { status: 'error', progress: 0, content: '', error: data }
        break

      case 'judge:start':
        judge.value = { status: 'running', progress: 70, content: '' }
        break
      case 'judge:content':
        judge.value.content += data || ''
        break
      case 'judge:done':
        judge.value = { status: 'completed', progress: 100, content: judge.value.content }
        break
      case 'judge:error':
        judge.value = { status: 'error', progress: 0, content: '', error: data }
        break

      case 'verdict':
        verdict.value = data
        break
    }
  }

  return {
    stockCode,
    isAnalyzing,
    error,
    bull,
    bear,
    judge,
    verdict,
    baseAgents,
    isBasePhase,
    dataSources,
    isDataPhase,
    factorItems,
    isFactorPhase,
    factorResults,
    bullContent,
    bearContent,
    judgeContent,
    isBullCompleted,
    isBearCompleted,
    isJudgeCompleted,
    isAllCompleted,
    baseCompletedCount,
    baseTotal,
    overallProgress,
    phase,
    reset,
    startDebate,
  }
})
