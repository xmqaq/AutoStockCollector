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
}