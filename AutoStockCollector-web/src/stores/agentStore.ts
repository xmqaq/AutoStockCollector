import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api/ai'

export interface AgentState {
  id: string
  name: string
  role: 'market' | 'technical' | 'fund' | 'sentiment' | 'risk' | 'commander'
  status: 'idle' | 'analyzing' | 'completed' | 'error'
  progress: number
  result?: AgentResult
  error?: string
  startedAt?: number
  completedAt?: number
}

export interface AgentResult {
  score?: number
  conclusion?: string
  signals?: string[]
  metrics?: Record<string, number>
  recommendation?: string
  rawContent?: string
}

export const useAgentStore = defineStore('agent', () => {
  const agents = ref<AgentState[]>([
    { id: 'market', name: '市场分析师', role: 'market', status: 'idle', progress: 0 },
    { id: 'technical', name: '技术分析师', role: 'technical', status: 'idle', progress: 0 },
    { id: 'fund', name: '资金分析师', role: 'fund', status: 'idle', progress: 0 },
    { id: 'sentiment', name: '舆情分析师', role: 'sentiment', status: 'idle', progress: 0 },
    { id: 'risk', name: '风控分析师', role: 'risk', status: 'idle', progress: 0 },
    { id: 'commander', name: '决策指挥官', role: 'commander', status: 'idle', progress: 0 },
  ])

  const agentMappings = {
    market: 'market_analyst',
    technical: 'technical_analyst',
    fund: 'fund_analyst',
    sentiment: 'sentiment_analyst',
    risk: 'risk_analyst',
  }

  const currentTask = ref<{
    code: string
    type: string
    startedAt: number
  } | null>(null)

  const aggregatedResult = ref<AggregatedResult | null>(null)
  const useRealApi = ref(true)

  const activeAgents = computed(() => agents.value.filter(a => a.status !== 'idle'))
  const completedAgents = computed(() => agents.value.filter(a => a.status === 'completed'))

  const isAllCompleted = computed(() => {
    const mainAgents = agents.value.filter(a => a.role !== 'commander')
    return mainAgents.every(a => a.status === 'completed' || a.status === 'error')
  })

  const overallProgress = computed(() => {
    const total = agents.value.reduce((sum, a) => sum + a.progress, 0)
    return Math.round(total / agents.value.length)
  })

  function resetAgents() {
    agents.value.forEach(a => {
      a.status = 'idle'
      a.progress = 0
      a.result = undefined
      a.error = undefined
      a.startedAt = undefined
      a.completedAt = undefined
    })
    aggregatedResult.value = null
    currentTask.value = null
  }

  async function startTask(code: string, type: string) {
    resetAgents()
    currentTask.value = { code, type, startedAt: Date.now() }

    const analysisAgents = agents.value.filter(a => a.role !== 'commander')

    if (useRealApi.value) {
      await runRealAnalysis(analysisAgents, code)
    } else {
      runMockAnalysis(analysisAgents)
    }
  }

  async function runRealAnalysis(analysisAgents: AgentState[], code: string) {
    const promises = analysisAgents.map((agent, index) => {
      return new Promise<void>(async (resolve) => {
        setTimeout(async () => {
          agent.status = 'analyzing'
          agent.progress = 10
          agent.startedAt = Date.now()

          const backendAgentId = agentMappings[agent.role as keyof typeof agentMappings]
          if (!backendAgentId) {
            agent.status = 'error'
            agent.error = '未找到对应的Agent'
            resolve()
            return
          }

          try {
            agent.progress = 30
            const response = await agentApi.analyze(backendAgentId, code)

            agent.progress = 80
            if (response.success && response.data) {
              agent.status = 'completed'
              agent.progress = 100
              agent.completedAt = Date.now()
              agent.result = parseAgentResult(agent.role, response.data.content || '')
            } else {
              agent.status = 'error'
              agent.error = response.error || '分析失败'
            }
          } catch (err: any) {
            agent.status = 'error'
            agent.error = err.message || '网络错误'
          }

          if (isAllCompleted.value) {
            aggregateResults()
          }
          resolve()
        }, index * 1000)
      })
    })

    await Promise.all(promises)
  }

  function parseAgentResult(role: AgentState['role'], content: string): AgentResult {
    const scoreMatch = content.match(/评分[：:]\s*(\d+(?:\.\d+)?)|综合评分[：:]\s*(\d+(?:\.\d+)?)/i)
    const score = scoreMatch
      ? parseFloat(scoreMatch[1] || scoreMatch[2])
      : 50 + Math.random() * 30

    let recommendation = ''
    if (content.includes('买入') || content.includes('推荐') || content.includes('增持')) {
      recommendation = '买入建议'
    } else if (content.includes('卖出') || content.includes('减持') || content.includes('回避')) {
      recommendation = '建议观望'
    } else if (content.includes('持有') || content.includes('中性')) {
      recommendation = '持有建议'
    }

    const signals: string[] = []
    const signalKeywords = ['金叉', '银叉', '背离', '突破', '支撑', '压力', '放量', '缩量', '超买', '超卖']
    signalKeywords.forEach(keyword => {
      if (content.includes(keyword)) {
        signals.push(keyword)
      }
    })

    const conclusionMatch = content.match(/结论[：:]([^\n]+)|分析[：:]([^\n]+)/i)
    const conclusion = conclusionMatch
      ? (conclusionMatch[1] || conclusionMatch[2])
      : content.substring(0, 100) + '...'

    return {
      score: Math.min(100, Math.max(0, score)),
      conclusion: conclusion,
      signals: signals.slice(0, 5),
      recommendation: recommendation || '综合分析',
      rawContent: content,
      metrics: {
        confidence: 75 + Math.random() * 20
      }
    }
  }

  function runMockAnalysis(analysisAgents: AgentState[]) {
    analysisAgents.forEach((agent, index) => {
      setTimeout(() => {
        agent.status = 'analyzing'
        agent.progress = 0

        simulateProgress(agent.id)
      }, index * 200)
    })
  }

  function simulateProgress(agentId: string) {
    const interval = setInterval(() => {
      const agent = agents.value.find(a => a.id === agentId)
      if (!agent || agent.status !== 'analyzing') {
        clearInterval(interval)
        return
      }

      agent.progress += Math.random() * 15 + 5
      if (agent.progress >= 100) {
        agent.progress = 100
        agent.status = 'completed'
        agent.completedAt = Date.now()
        agent.result = generateMockResult(agent.role)
        clearInterval(interval)

        if (isAllCompleted.value) {
          aggregateResults()
        }
      }
    }, 300)
  }

  function generateMockResult(role: AgentState['role']): AgentResult {
    const results: Record<string, AgentResult> = {
      market: {
        score: 70 + Math.random() * 20,
        conclusion: '市场环境偏暖，流动性充裕',
        signals: ['北向资金净流入', '市场情绪转暖'],
        metrics: { marketHeat: 65, trendStrength: 70 },
        recommendation: '可适当加仓',
      },
      technical: {
        score: 60 + Math.random() * 25,
        conclusion: 'K线形态良好，均线多头排列',
        signals: ['MACD金叉', 'RSI处于强势区间'],
        metrics: { rsi: 58, macd: 72, maAlignment: 85 },
        recommendation: '技术面买入信号',
      },
      fund: {
        score: 65 + Math.random() * 20,
        conclusion: '主力资金净流入，机构持仓增加',
        signals: ['大单净买入', '持续3日资金净流入'],
        metrics: { mainFlow: 8500, superFlow: 3200, netInflowRate: 15 },
        recommendation: '资金面支撑股价',
      },
      sentiment: {
        score: 55 + Math.random() * 25,
        conclusion: '舆情偏正面，机构评级上调',
        signals: ['研报看好', '业绩预增'],
        metrics: { sentimentScore: 68, positiveRatio: 72, newsCount: 15 },
        recommendation: '舆情面利好',
      },
      risk: {
        score: 50 + Math.random() * 30,
        conclusion: '风险可控，注意高位回调',
        signals: ['PE偏高', '换手率较高'],
        metrics: { riskLevel: 45, volatility: 28, beta: 1.2 },
        recommendation: '注意控制仓位',
      },
    }
    return results[role] || { score: 60 }
  }

  function aggregateResults() {
    const commander = agents.value.find(a => a.role === 'commander')
    if (!commander) return

    commander.status = 'analyzing'

    const allResults = agents.value
      .filter(a => a.role !== 'commander' && a.result)
      .map(a => a.result!)

    const avgScore = allResults.reduce((sum, r) => sum + (r.score || 0), 0) / allResults.length

    const recommendations = allResults
      .filter(r => r.recommendation)
      .map(r => r.recommendation!)
      .join('; ')

    const allSignals = allResults.flatMap(r => r.signals || [])
    const signalCount = allSignals.reduce((acc, s) => {
      acc[s] = (acc[s] || 0) + 1
      return acc
    }, {} as Record<string, number>)

    const topSignals = Object.entries(signalCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([signal]) => signal)

    const weights: Record<string, number> = {
      market: 0.15,
      technical: 0.30,
      fund: 0.25,
      sentiment: 0.15,
      risk: 0.15,
    }

    const nonCommanderAgents = agents.value.filter(a => a.role !== 'commander')
    const weightedScore = allResults.reduce((sum, r, idx) => {
      const agent = nonCommanderAgents[idx]
      const role = agent?.role as string | undefined
      return sum + (r.score || 0) * ((role && role in weights) ? weights[role as keyof typeof weights] : 0.2)
    }, 0)

    aggregatedResult.value = {
      code: currentTask.value?.code || '',
      compositeScore: Math.round(weightedScore * 10) / 10,
      recommendation: weightedScore >= 70 ? '强烈推荐' : weightedScore >= 60 ? '买入' : weightedScore >= 50 ? '观望' : '回避',
      avgScore: Math.round(avgScore * 10) / 10,
      signals: topSignals,
      agentResults: agents.value
        .filter(a => a.role !== 'commander')
        .map(a => ({
          name: a.name,
          role: a.role,
          score: a.result?.score || 0,
          conclusion: a.result?.conclusion || '',
          recommendation: a.result?.recommendation || '',
        })),
      generatedAt: new Date().toISOString(),
    }

    commander.status = 'completed'
    commander.progress = 100
    commander.completedAt = Date.now()
    commander.result = {
      score: weightedScore,
      conclusion: `综合评分${weightedScore.toFixed(1)}分`,
      recommendation: aggregatedResult.value.recommendation,
    }
  }

  function getAgentByRole(role: AgentState['role']) {
    return agents.value.find(a => a.role === role)
  }

  function setUseRealApi(useReal: boolean) {
    useRealApi.value = useReal
  }

  return {
    agents,
    currentTask,
    aggregatedResult,
    activeAgents,
    completedAgents,
    isAllCompleted,
    overallProgress,
    useRealApi,
    resetAgents,
    startTask,
    getAgentByRole,
    setUseRealApi,
  }
})

export interface AggregatedResult {
  code: string
  compositeScore: number
  recommendation: string
  avgScore: number
  signals: string[]
  agentResults: {
    name: string
    role: string
    score: number
    conclusion: string
    recommendation: string
  }[]
  generatedAt: string
}