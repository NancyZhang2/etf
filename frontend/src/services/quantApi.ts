import api from './api'
import type {
  StrategyItem,
  StrategyDetail,
  BacktestResult,
  YearlyBacktest,
  PortfolioRecord,
  SignalItem,
  SignalHistoryItem,
  VirtualAccountSummary,
  VirtualTradeItem,
  VirtualNavPoint,
} from '@/types/api'

export function getStrategies(categoryId?: number): Promise<StrategyItem[]> {
  return api.get('/strategies', { params: categoryId ? { category_id: categoryId } : {} })
}

export function getStrategyDetail(id: number): Promise<StrategyDetail> {
  return api.get(`/strategies/${id}`)
}

export function getBacktest(id: number, year?: number): Promise<BacktestResult> {
  return api.get(`/strategies/${id}/backtest`, { params: year ? { year } : {} })
}

export function runCustomBacktest(
  id: number,
  params: Record<string, unknown>,
): Promise<BacktestResult> {
  return api.post(`/strategies/${id}/backtest`, { params })
}

export function getBacktestYearly(id: number): Promise<YearlyBacktest[]> {
  return api.get(`/strategies/${id}/backtest/yearly`)
}

export function getPortfolio(id: number): Promise<PortfolioRecord[]> {
  return api.get(`/strategies/${id}/portfolio`)
}

export function getSignalsLatest(strategyId?: number): Promise<SignalItem[]> {
  return api.get('/signals/latest', {
    params: strategyId ? { strategy_id: strategyId } : {},
  })
}

export function getSignalHistory(params: {
  strategy_id?: number
  etf_code?: string
  start_date?: string
  end_date?: string
}): Promise<SignalHistoryItem[]> {
  return api.get('/signals/history', { params })
}

// ── Virtual Portfolio ──

export function getVirtualSummary(id: number): Promise<VirtualAccountSummary> {
  return api.get(`/strategies/${id}/virtual/summary`)
}

export function getVirtualNav(id: number): Promise<VirtualNavPoint[]> {
  return api.get(`/strategies/${id}/virtual/nav`)
}

export function getVirtualTrades(
  id: number,
  params?: { start_date?: string; end_date?: string },
): Promise<VirtualTradeItem[]> {
  return api.get(`/strategies/${id}/virtual/trades`, { params })
}

export function startVirtualAccount(
  id: number,
  initialCapital?: number,
): Promise<{ account_id: number; strategy_id: number; initial_capital: number; cash: number }> {
  return api.post(`/strategies/${id}/virtual/start`, initialCapital ? { initial_capital: initialCapital } : {})
}
