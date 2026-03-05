import { useParams, Link } from 'react-router-dom'
import { useState } from 'react'
import { useApi } from '@/hooks/useApi'
import {
  getStrategyDetail,
  getBacktest,
  getBacktestYearly,
  getPortfolio,
  getSignalsLatest,
  runCustomBacktest,
} from '@/services/quantApi'
import Loading from '@/components/common/Loading'
import ErrorDisplay from '@/components/common/ErrorDisplay'
import Card from '@/components/common/Card'
import MetricCard from '@/components/common/MetricCard'
import SignalBadge from '@/components/common/SignalBadge'
import BarChart from '@/components/charts/BarChart'
import LineChart from '@/components/charts/LineChart'
import { formatPercent, formatNumber, formatDate } from '@/utils/format'
import type { BacktestResult } from '@/types/api'

export default function StrategyDetail() {
  const { id } = useParams<{ id: string }>()
  const strategyId = Number(id)

  const detail = useApi(() => getStrategyDetail(strategyId), [strategyId])
  const backtest = useApi(() => getBacktest(strategyId), [strategyId])
  const yearly = useApi(() => getBacktestYearly(strategyId), [strategyId])
  const portfolio = useApi(() => getPortfolio(strategyId), [strategyId])
  const signals = useApi(() => getSignalsLatest(strategyId), [strategyId])

  const [customParams, setCustomParams] = useState<Record<string, unknown>>({})
  const [customBt, setCustomBt] = useState<BacktestResult | null>(null)
  const [runningBt, setRunningBt] = useState(false)
  const [btError, setBtError] = useState<string | null>(null)

  if (detail.loading) return <Loading />
  if (detail.error) return <ErrorDisplay message={detail.error} onRetry={detail.reload} />
  if (!detail.data) return <ErrorDisplay message="策略不存在" />

  const s = detail.data
  const bt = customBt || backtest.data
  const yearlyData = yearly.data || []
  const portfolioData = portfolio.data || []
  const signalData = signals.data || []

  // Build NAV chart data
  const navDates: string[] = []
  const navValues: (number | null)[] = []
  const seen = new Set<string>()
  for (const p of portfolioData) {
    if (!seen.has(p.trade_date) && p.nav != null) {
      seen.add(p.trade_date)
      navDates.push(p.trade_date)
      navValues.push(p.nav)
    }
  }

  const handleParamChange = (key: string, value: string) => {
    const numVal = Number(value)
    setCustomParams((prev) => ({
      ...prev,
      [key]: isNaN(numVal) ? value : numVal,
    }))
  }

  const handleRunBacktest = async () => {
    setRunningBt(true)
    setBtError(null)
    try {
      const merged = { ...(s.default_params || {}), ...(s.params || {}), ...customParams }
      const result = await runCustomBacktest(strategyId, merged)
      setCustomBt(result)
    } catch (err) {
      setBtError(err instanceof Error ? err.message : '回测失败')
    } finally {
      setRunningBt(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link to="/strategy" className="text-sm text-gray-400 hover:text-primary">&larr; 返回策略列表</Link>
        <h2 className="text-xl font-bold mt-2">{s.name}</h2>
        <p className="text-sm text-gray-500 mt-1">{s.description}</p>
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded">{s.strategy_type}</span>
          <span className={`text-xs px-2 py-0.5 rounded ${s.is_active ? 'bg-fall/10 text-fall' : 'bg-gray-100 text-gray-400'}`}>
            {s.is_active ? '运行中' : '已停用'}
          </span>
        </div>
      </div>

      {/* Parameter panel */}
      <Card title="策略参数" extra={
        <button
          onClick={handleRunBacktest}
          disabled={runningBt}
          className="px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary/90 disabled:opacity-50"
        >
          {runningBt ? '回测中...' : '运行回测'}
        </button>
      }>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(s.params || {}).map(([key, val]) => (
            <div key={key}>
              <label className="text-xs text-gray-500 block mb-1">{key}</label>
              <input
                type="text"
                defaultValue={String(val)}
                onChange={(e) => handleParamChange(key, e.target.value)}
                className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:border-primary"
              />
            </div>
          ))}
        </div>
        {btError && <div className="text-xs text-rise mt-2">{btError}</div>}
        {customBt && <div className="text-xs text-fall mt-2">自定义参数回测结果已更新</div>}
      </Card>

      {/* Metrics dashboard */}
      {bt && (
        <Card title="回测指标">
          <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
            <MetricCard
              label="年化收益"
              value={formatPercent(bt.annual_return)}
              color={(bt.annual_return ?? 0) >= 0 ? 'rise' : 'fall'}
            />
            <MetricCard
              label="最大回撤"
              value={formatPercent(bt.max_drawdown)}
              color="fall"
            />
            <MetricCard label="夏普比率" value={formatNumber(bt.sharpe_ratio)} />
            <MetricCard label="索提诺" value={formatNumber(bt.sortino_ratio)} />
            <MetricCard label="卡尔玛" value={formatNumber(bt.calmar_ratio)} />
            <MetricCard label="胜率" value={formatPercent(bt.win_rate)} />
            <MetricCard label="盈亏比" value={formatNumber(bt.profit_loss_ratio)} />
            <MetricCard label="总交易次数" value={String(bt.total_trades ?? '--')} />
            <MetricCard
              label="基准收益"
              value={formatPercent(bt.benchmark_return)}
              color={(bt.benchmark_return ?? 0) >= 0 ? 'rise' : 'fall'}
            />
            <MetricCard
              label="超额收益"
              value={formatPercent(bt.excess_return)}
              color={(bt.excess_return ?? 0) >= 0 ? 'rise' : 'fall'}
            />
          </div>
        </Card>
      )}

      {/* Charts row */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Yearly bar chart */}
        {yearlyData.length > 0 && (
          <Card title="逐年收益">
            <BarChart
              labels={yearlyData.map((y) => String(y.year))}
              values={yearlyData.map((y) => y.annual_return)}
              height={280}
            />
          </Card>
        )}

        {/* NAV line chart */}
        {navDates.length > 0 && (
          <Card title="净值曲线">
            <LineChart
              dates={navDates}
              series={[
                { name: '策略净值', data: navValues, color: '#3b82f6', areaStyle: true },
              ]}
              height={280}
            />
          </Card>
        )}
      </div>

      {/* Recent signals */}
      <Card title="最近信号">
        {signalData.length === 0 ? (
          <div className="text-gray-400 text-sm text-center py-4">暂无信号</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left bg-gray-50">
                  <th className="px-3 py-2 font-medium text-gray-500">日期</th>
                  <th className="px-3 py-2 font-medium text-gray-500">ETF</th>
                  <th className="px-3 py-2 font-medium text-gray-500">信号</th>
                  <th className="px-3 py-2 font-medium text-gray-500 hidden md:table-cell">原因</th>
                </tr>
              </thead>
              <tbody>
                {signalData.slice(0, 20).map((sig, i) => (
                  <tr key={i} className="border-t border-gray-50">
                    <td className="px-3 py-2 text-gray-500">{formatDate(sig.signal_date)}</td>
                    <td className="px-3 py-2">
                      <Link to={`/etf/${sig.etf_code}`} className="text-primary">{sig.etf_code}</Link>
                      <span className="text-xs text-gray-400 ml-1">{sig.etf_name}</span>
                    </td>
                    <td className="px-3 py-2"><SignalBadge signal={sig.signal} /></td>
                    <td className="px-3 py-2 text-xs text-gray-500 hidden md:table-cell max-w-xs truncate">{sig.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
