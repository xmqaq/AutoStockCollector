import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { philosophyApi, type PhilosophyAgent, type PhilosophySignal } from '@/api/ai'

export const usePhilosophyStore = defineStore('philosophy', () => {
  const stockCode = ref('')
  const isAnalyzing = ref(false)
  const error = ref('')

  const agents = ref<PhilosophyAgent[]>([])
  const selectedIds = ref<string[]>([])
  const agentSignals = ref<PhilosophySignal[]>([])
  const verdict = ref<any>(null)

  const loaded = ref(false)

  const selectedAgents = computed(() =>
    agents.value.filter(a => selectedIds.value.includes(a.id))
  )

  const phase = ref<'idle' | 'data' | 'factor' | 'agent' | 'verdict' | 'done'>('idle')
  const overallProgress = computed(() => {
    if (phase.value === 'done' || phase.value === 'verdict') return 100
    if (phase.value === 'agent') {
      const done = agentSignals.value.length
      const total = selectedIds.value.length || 1
      return 30 + Math.round((done / total) * 60)
    }
    if (phase.value === 'factor') return 25
    if (phase.value === 'data') return 10
    return 0
  })

  const isAllCompleted = computed(() =>
    phase.value === 'done' || phase.value === 'verdict'
  )

  function reset() {
    stockCode.value = ''
    isAnalyzing.value = false
    error.value = ''
    agentSignals.value = []
    verdict.value = null
    phase.value = 'idle'
  }

  function toggleAgent(id: string) {
    const idx = selectedIds.value.indexOf(id)
    if (idx >= 0) {
      selectedIds.value.splice(idx, 1)
    } else {
      selectedIds.value.push(id)
    }
  }

  function selectAll() {
    selectedIds.value = agents.value.map(a => a.id)
  }

  function deselectAll() {
    selectedIds.value = []
  }

  async function loadAgents() {
    if (loaded.value) return
    try {
      const res = await philosophyApi.listAgents()
      if (res.data?.success && Array.isArray(res.data.data)) {
        const schools: Record<string, string> = {
          value: '价值派', growth: '成长派', technical: '技术派',
          macro: '宏观派', quant: '量化派', hot_money: '游资派',
          risk: '风控派', sentiment: '舆情派',
        }
        agents.value = res.data.data.map((a: any) => ({
          id: a.agent_id || a.id,
          name: a.name,
          school: a.archetype || a.school || 'other',
          school_label: schools[a.archetype] || a.school_label || '',
          description: a.description || '',
          enabled: true,
        }))
        loaded.value = true
      }
    } catch {
      agents.value = getDefaultAgents()
      loaded.value = true
    }
  }

  async function startAnalysis(code: string, agentIds: string[]) {
    reset()
    stockCode.value = code
    selectedIds.value = agentIds
    isAnalyzing.value = true

    try {
      const response = await philosophyApi.stream({ code, agents: agentIds })
      if (!response.ok || !response.body) {
        error.value = '无法连接分析服务'
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
      error.value = err.message || '分析流中断'
    } finally {
      isAnalyzing.value = false
    }
  }

  function handleEvent(parsed: any) {
    const type = parsed.type
    const data = parsed.data

    switch (type) {
      case 'start':
        phase.value = 'data'
        break
      case 'data:start':
        phase.value = 'data'
        break
      case 'data:done':
        phase.value = 'factor'
        break
      case 'factor:start':
        phase.value = 'factor'
        break
      case 'factor:done':
        phase.value = 'agent'
        break
      case 'agent:done':
        if (data) {
          const sig = data.signal || {}
          agentSignals.value.push({
            agent_id: data.agent_id,
            agent_name: data.agent_name || data.agent_id,
            philosophy: sig.philosophy || '',
            archetype: sig.archetype || '',
            score: sig.score || 0,
            action: sig.action || 'hold',
            confidence: sig.confidence || 0,
            reasoning: sig.reasoning || '',
            signals: sig.signals || [],
            key_factors: sig.key_factors || [],
            risk_warnings: sig.risk_warnings || [],
          })
        }
        break
      case 'verdict':
        verdict.value = data
        phase.value = 'verdict'
        break
      case 'done':
        phase.value = 'done'
        break
      case 'error':
        error.value = data?.message || data || '分析错误'
        phase.value = 'done'
        break
    }
  }

  return {
    stockCode,
    isAnalyzing,
    error,
    agents,
    selectedIds,
    agentSignals,
    verdict,
    loaded,
    selectedAgents,
    phase,
    overallProgress,
    isAllCompleted,
    reset,
    toggleAgent,
    selectAll,
    deselectAll,
    loadAgents,
    startAnalysis,
  }
})

function getDefaultAgents(): PhilosophyAgent[] {
  const schools: Record<string, string> = {
    value: '价值派',
    growth: '成长派',
    technical: '技术派',
    macro: '宏观派',
    quant: '量化派',
    hot_money: '游资派',
    risk: '风控派',
    sentiment: '舆情派',
  }

  const defaultAgents: [string, string, string][] = [
    ['buffett', '巴菲特 (价值投资)', 'value'],
    ['graham', '格雷厄姆 (安全边际)', 'value'],
    ['burry', 'Burry (深度价值)', 'value'],
    ['damodaran', '达摩达兰 (估值分析)', 'value'],
    ['fisher', '费雪 (成长价值)', 'growth'],
    ['lynch', '彼得林奇 (PEG成长)', 'growth'],
    ['trend', '趋势跟踪者', 'technical'],
    ['momentum', '动量交易者', 'technical'],
    ['dalio', '达利欧 (宏观经济)', 'macro'],
    ['simons', '西蒙斯 (量化)', 'quant'],
    ['dragon', '游资操盘手', 'hot_money'],
    ['risk_manager', '风控官', 'risk'],
    ['sentiment', '舆情分析师', 'sentiment'],
  ]

  return defaultAgents.map(([id, name, school]) => ({
    id,
    name,
    school,
    school_label: schools[school] || school,
    description: '',
    enabled: true,
  }))
}
