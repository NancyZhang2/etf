// ── API Response Envelope ──
export interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

// ── Data Module ──
export interface EtfBasicInfo {
  code: string
  name: string
  category: string
  exchange: string
  list_date?: string
}

export interface EtfCategory {
  category: string
  count: number
}

export interface EtfDailyData {
  trade_date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  amount: number | null
}

export interface DataStatus {
  last_sync: string | null
  record_count: number
  etf_count: number
  status: string
}

export interface TradingCalendarDay {
  date: string
  is_trading_day: boolean
}

// ── Quant Module ──
export interface StrategyItem {
  id: number
  name: string
  category: string
  strategy_type: string
  description: string
  is_active: boolean
}

export interface StrategyDetail {
  id: number
  name: string
  strategy_type: string
  description: string
  params: Record<string, unknown>
  default_params: Record<string, unknown>
  etf_pool: string[]
  is_active: boolean
}

export interface BacktestResult {
  year?: number
  total_return?: number
  annual_return: number | null
  max_drawdown: number | null
  annual_volatility?: number | null
  sharpe_ratio: number | null
  sortino_ratio: number | null
  calmar_ratio: number | null
  win_rate: number | null
  profit_loss_ratio: number | null
  total_trades: number | null
  benchmark_return: number | null
  excess_return: number | null
}

export interface YearlyBacktest {
  year: number
  annual_return: number | null
  max_drawdown: number | null
  sharpe_ratio: number | null
  sortino_ratio: number | null
  calmar_ratio: number | null
  win_rate: number | null
  total_trades: number | null
}

export interface PortfolioRecord {
  trade_date: string
  etf_code: string
  position: number | null
  nav: number | null
  daily_return: number | null
}

export interface SignalItem {
  strategy_name: string
  etf_code: string
  etf_name: string | null
  signal: 'BUY' | 'SELL' | 'HOLD'
  target_weight: number | null
  reason: string | null
  signal_date: string
}

export interface SignalHistoryItem {
  signal_date: string
  signal: 'BUY' | 'SELL' | 'HOLD'
  reason: string | null
}

// ── Research Module ──
export interface ResearchReportItem {
  id: number
  title: string
  source: string
  report_date: string | null
  summary: string | null
  etf_code: string | null
}

export interface ResearchReportList {
  total: number
  items: ResearchReportItem[]
}

export interface ResearchReportDetail {
  id: number
  title: string
  source: string
  content: string | null
  analysis: ResearchAnalysis | null
  report_date: string | null
  etf_code: string | null
  created_at: string | null
}

export interface ResearchAnalysis {
  summary?: string
  sentiment?: string
  confidence?: number
  macro_view?: {
    economy?: string
    liquidity?: string
    policy?: string
  }
  risk_factors?: string[]
  key_points?: string[]
  etf_relevance?: {
    code?: string
    sentiment?: string
    confidence?: number
  } | string
}

export interface ResearchFramework {
  etf_code: string
  week_date: string | null
  fundamental_score: number | null
  technical_score: number | null
  sentiment_score: number | null
  overall_score: number | null
  framework_data: Record<string, unknown> | null
}

export interface SentimentStats {
  bullish_count: number
  bearish_count: number
  neutral_count: number
  overall_sentiment: string
}

export interface MacroConsensus {
  economy: string | null
  liquidity: string | null
  policy: string | null
  key_points: string[] | null
  updated_at: string | null
}
