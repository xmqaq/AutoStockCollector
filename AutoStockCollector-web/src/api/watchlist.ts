import client from './client'

export const watchlistApi = {
  getWatchlist() {
    return client.get('/api/v1/watchlist')
  },

  addWatchlist(data: { code: string; priority?: number }) {
    return client.post('/api/v1/watchlist', data)
  },

  removeWatchlist(code: string) {
    return client.delete(`/api/v1/watchlist/${code}`)
  },

  list() {
    return client.get('/api/v1/watchlist')
  },
}
