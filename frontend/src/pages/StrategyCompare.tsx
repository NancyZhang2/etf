import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '@/hooks/useApi'
import { getStrategies, getBacktest } from '@/services/quantApi'
import Loading from '@/components/common/Loading'
import ErrorDisplay from '@/components/common/ErrorDisplay'
import Card from '@/components/common/Card'
import BarChart from '@/components/charts/BarChart'
import { formatPercent, formatNumber } from '@/utils/format'
import type { StrategyItem, BacktestResult } from '@/types/api'

const MAX_COMPARE = 4

export default function StrategyCompare() {
  const strategies = useApi(() => getStrategies())
  const [selected, setSelected] = useState<number[]>([])
  const [backtests, setBacktests] = useState<Record<number, BacktestResult>>({})
  const [loading, setLoading] = useState(false)

  // Fetch backtest results when selection changes
  useEffect(() => {
    if (selected.length === 0) {
      setBacktests({})
      return
    }
    setLoading(true)
    const fetches = selected.map((id) =>
      getBacktest(id).then((bt) => ({ id, bt })).catch(() => null),
    )
    Promise.all(fetches).then((results) => {
      const map: Record<number, BacktestResult> = {}
      for (const r of results) {
        if (r) map[r.id] = r.bt
      }
      setBacktests(map)
      setLoading(false)
    })
  }, [selected])

  const toggleStrategy = (id: number) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= MAX_COMPARE) return prev
      return [...prev, id]
    })
  }

  const strategyMap = useMemo(() => {
    const map: Record<number, StrategyItem> = {}
    for (const s of strategies.data || []) map[s.id] = s
    return map
  }, [strategies.data])

  if (strategies.loading) return <Loading />
  if (strategies.error) return <ErrorDisplay message={strategies.error} onRetry={strategies.reload} />

  const allStrategies = strategies.data || []
  const selectedStrategies = selected.map((id) => strategyMap[id]).filter(Boolean)

  // Metric rows for comparison table
  const metrics: { key: keyof BacktestResult; label: string; format: (v: number | null) => string; colorize?: boolean }[] = [
    { key: 'annual_return', label: '年化收益', format: formatPercent, colorize: true },
    { key: 'max_drawdown', label: '最大回撤', format: formatPercent },
    { key: 'sharpe_ratio', label: '夏普比率', format: formatNumber },
    { key: 'sortino_ratio', label: '索提诺比率', format: formatNumber },
    { key: 'calmar_ratio', label: '卡尔玛比率', format: formatNumber },
    { key: 'win_rate', label: '胜率', format: formatPercent },
    { key: 'profit_loss_ratio', label: '盈亏比', format: formatNumber },
    { key: 'total_trades', label: '总交易次数', format: (v) => v != null ? String(v) : '--' },
    { key: 'benchmark_return', label: '基准收益', format: formatPercent, colorize: true },
    { key: 'excess_return', label: '超额收益', format: formatPercent, colorize: true },
  ]

  // Find best value for each metric (for highlighting)
  const bestValues: Record<string, number> = {}
  for (const m of metrics) {
    let best: number | null = null
    for (const id of selected) {
      const bt = backtests[id]
      if (!bt) continue
      const val = bt[m.key] as number | null
      if (val == null) continue
      // For max_drawdown, less negative is better
      const compare = m.key === 'max_drawdown' ? -Math.abs(val) : val
      if (best === null || compare > best) best = compare
    }
    if (best !== null) bestValues[m.key] = best
  }

  const isBest = (metricKey: string, val: number | null): boolean => {
    if (val == null || !(metricKey in bestValues)) return false
    const compare = metricKey === 'max_drawdown' ? -Math.abs(val) : val
    return compare === bestValues[metricKey]
  }

  return (
    <div className="space-y-6">
      <div>
        <Link to="/strategy" className="text-sm text-gray-400 hover:text-primary">&larr; 返回策略列表</Link>
        <h2 className="text-xl font-bold mt-2">策略对比</h2>
        <p className="text-sm text-gray-500 mt-1">选择 2~{MAX_COMPARE} 个策略进行并排对比</p>
      </div>

      {/* Strategy selector */}
      <Card title={`选择策略（已选 ${selected.length}/{MAX_COMPARE}）`}>
        <div className="flex flex-wrap gap-2">
          {allStrategies.map((s) => {
            const isSelected = selected.includes(s.id)
            return (
              <button
                key={s.id}
                onClick={() => toggleStrategy(s.id)}
                disabled={!isSelected && selected.length >= MAX_COMPARE}
                className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  isSelected
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed'
                }`}
              >
                {s.name}
              </button>
            )
          })}
        </div>
      </Card>

      {/* Comparison content */}
      {selected.length < 2 ? (
        <div className="text-center text-gray-400 py-10">请至少选择 2 个策略进行对比</div>
      ) : loading ? (
        <Loading />
      ) : (
        <>
          {/* Metrics comparison table */}
          <Card title="指标对比">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-3 py-2 text-left font-medium text-gray-500 sticky left-0 bg-gray-50">指标</th>
                    {selectedStrategies.map((s) => (
                      <th key={s.id} className="px-3 py-2 text-center font-medium text-gray-900 min-w-[120px]">
                        <Link to={`/strategy/${s.id}`} className="text-primary hover:underline">{s.name}</Link>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {metrics.map((m) => (
                    <tr key={m.key} className="border-t border-gray-50">
                      <td className="px-3 py-2 text-gray-500 sticky left-0 bg-white">{m.label}</td>
                      {selected.map((id) => {
                        const bt = backtests[id]
                        const val = bt ? (bt[m.key] as number | null) : null
                        const best = bt ? isBest(m.key, val) : false
                        let colorClass = 'text-gray-900'
                        if (m.colorize && val != null) {
                          colorClass = val >= 0 ? 'text-rise' : 'text-fall'
                        }
                        if (m.key === 'max_drawdown' && val != null) {
                          colorClass = 'text-fall'
                        }
                        return (
                          <td key={id} className={`px-3 py-2 text-center ${colorClass} ${best ? 'font-bold' : ''}`}>
                            {bt ? m.format(val) : '--'}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Bar chart comparison */}
          <div className="grid lg:grid-cols-2 gap-6">
            <Card title="年化收益对比">
              <BarChart
                labels={selectedStrategies.map((s) => s.name)}
                values={selected.map((id) => backtests[id]?.annual_return ?? null)}
                height={280}
              />
            </Card>
            <Card title="最大回撤对比">
              <BarChart
                labels={selectedStrategies.map((s) => s.name)}
                values={selected.map((id) => backtests[id]?.max_drawdown ?? null)}
                height={280}
              />
            </Card>
            <Card title="夏普比率对比">
              <BarChart
                labels={selectedStrategies.map((s) => s.name)}
                values={selected.map((id) => backtests[id]?.sharpe_ratio ?? null)}
                height={280}
                risefall={false}
              />
            </Card>
            <Card title="胜率对比">
              <BarChart
                labels={selectedStrategies.map((s) => s.name)}
                values={selected.map((id) => backtests[id]?.win_rate ?? null)}
                height={280}
                risefall={false}
              />
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
