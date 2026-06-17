import client from './client'

export interface PlatformConfig {
  buy_commission_rate: number
  sell_commission_rate: number
  min_commission: number
  stamp_tax_rate: number
  updated_at?: string
}

export const platformConfigApi = {
  async get(): Promise<PlatformConfig> {
    const res = await client.get<{ data: PlatformConfig }>('/api/v1/platform-config')
    return res.data.data
  },

  async update(patch: Partial<PlatformConfig>): Promise<PlatformConfig> {
    const res = await client.put<{ data: PlatformConfig }>('/api/v1/platform-config', patch)
    return res.data.data
  },
}
