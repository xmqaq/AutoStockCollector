import client from './client'

export interface MarketIndex {
  code: string
  name: string
  price: number
  change: number
  change_amount: number
  volume: number
  amount: number
  amplitude?: number
  high?: number
  low?: number
  open?: number
  prev_close?: number
}

export interface StockQuote {
  code: string
  name: string
  price?: number
  change: number
  change_amount?: number
  volume?: number
  amount?: number
  open?: number
  high?: number
  low?: number
  prev_close?: number
  turnover?: number
}

export interface MinuteBar {
  time: string
  price: number
  volume: number
}

export interface SignalItem {
  code: string
  name?: string
  type: 'buy' | 'sell' | 'neutral'
  strength?: string
  price?: number
  time?: string
  reasons: string[]
}

export const marketApi = {
  getIndices() {
    return client.get('/api/v1/market/indices')
  },

  getRealtimeQuotes(codes: string[]) {
    return client.post('/api/v1/market/realtime-quotes', { codes })
  },

  getMinuteKline(code: string) {
    return client.get(`/api/v1/market/minute-kline/${encodeURIComponent(code)}`)
  },

  detectSignals(code: string) {
    return client.get(`/api/v1/market/signals/${encodeURIComponent(code)}`)
  },

  getSignalHistory(code?: string) {
    return client.get('/api/v1/market/signal-history', { params: { code } })
  },

  getValuationBatch(codes: string[]) {
    return client.post('/api/v1/valuation/batch', { codes })
  },
}