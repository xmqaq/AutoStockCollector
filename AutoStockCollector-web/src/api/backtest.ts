import client from './client'

export interface BacktestParams {
  strategy: string
  codes: string[]
  start_date: string
  end_date: string
  initial_cash: number
  stop_loss?: number
  take_profit?: number
}

export const backtestApi = {
  runBacktest(params: BacktestParams) {
    return client.post('/api/v1/backtest', params)
  },
}
