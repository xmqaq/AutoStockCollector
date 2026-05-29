import { reactive } from 'vue'
import request from './client'

export interface Position {
  code: string
  name?: string
  shares: number
  avg_cost: number
  current_price?: number
  market_value?: number
  pnl?: number
  pnl_percent?: number
  position_ratio?: number
  stop_loss: number
  target_price: number
}

interface PositionState {
  positions: Position[]
  loading: boolean
  error: string | null
}

const positionState = reactive<PositionState>({
  positions: [],
  loading: false,
  error: null
})

export const positionApi = {
  state: positionState,

  async loadPositions(): Promise<void> {
    positionState.loading = true
    positionState.error = null
    try {
      const res = await request.get<Position[]>('/api/position/list')
      positionState.positions = res.data || []
    } catch (error: any) {
      positionState.error = error.message || '加载失败'
      positionState.positions = []
    } finally {
      positionState.loading = false
    }
  },

  async list(): Promise<Position[]> {
    const res = await request.get<Position[]>('/api/position/list')
    return res.data || []
  },

  async addPosition(data: Partial<Position>): Promise<void> {
    await request.post('/api/position/save', data)
  },

  async updatePosition(data: Partial<Position>): Promise<void> {
    if (!data.code) return
    await request.put(`/api/position/update/${data.code}`, data)
  },

  async deletePosition(code: string): Promise<void> {
    await request.delete(`/api/position/delete?code=${code}`)
  },

  async batchSave(positions: Partial<Position>[]): Promise<void> {
    await request.post('/api/position/batch_save', { positions })
  },

  async getPortfolio(): Promise<any> {
    return request.get('/api/position/portfolio')
  },

  async getDistribution(): Promise<any> {
    return request.get('/api/position/distribution')
  },

  async getAlerts(): Promise<any> {
    return request.get('/api/position/alerts')
  },
}