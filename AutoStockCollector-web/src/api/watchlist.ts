import client from './client'

export interface WatchlistGroup {
  group_id: string
  name: string
  description: string
  stock_count: number
}

export const watchlistApi = {
  getWatchlist(groupId?: string) {
    const params = groupId ? `?group_id=${encodeURIComponent(groupId)}` : ''
    return client.get(`/api/v1/watchlist${params}`)
  },

  addWatchlist(data: { code: string; priority?: number; group_id?: string }) {
    return client.post('/api/v1/watchlist', data)
  },

  removeWatchlist(code: string) {
    return client.delete(`/api/v1/watchlist/${code}`)
  },

  updatePriority(code: string, priority: number) {
    return client.patch('/api/v1/watchlist/priority', { code, priority })
  },

  moveStock(code: string, groupId: string) {
    return client.patch('/api/v1/watchlist/move', { code, group_id: groupId })
  },

  batchAdd(codes: string[], groupId?: string) {
    return client.post('/api/v1/watchlist/batch', { codes, group_id: groupId })
  },

  batchRemove(codes: string[]) {
    return client.post('/api/v1/watchlist/batch-remove', { codes })
  },

  getGroups() {
    return client.get<{ success: boolean; data: WatchlistGroup[] }>('/api/v1/watchlist/groups')
  },

  createGroup(groupId: string, name: string, description?: string) {
    return client.post('/api/v1/watchlist/groups', { group_id: groupId, name, description })
  },

  deleteGroup(groupId: string) {
    return client.delete(`/api/v1/watchlist/groups/${encodeURIComponent(groupId)}`)
  },

  getAlerts(threshold?: number) {
    const params = threshold ? `?threshold=${threshold}` : ''
    return client.get(`/api/v1/watchlist/alerts${params}`)
  },
}
