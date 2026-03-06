import { useApi } from '@/hooks/useApi'
import { getStrategies, getBacktest } from '@/services/quantApi'
import Loading from '@/components/common/Loading'
import ErrorDisplay from '@/components/common/ErrorDisplay'
import Card from '@/components/common/Card'
import { formatPercent, formatNumber } from '@/utils/format'
import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import type { StrategyItem, BacktestResult } from '@/types/api'

export default function StrategyList() {
  const [activeTab, setActiveTab] = useState<string>('经典量化策略')
  const strategies = useApi(() => getStrategies())
  const [backtests, setBacktests] = useState<Record<number, BacktestResult>>({})
  const [btLoading, setBtLoading] = useState(false)

  // Fetch backtest results for all strategies
  useEffect(() => {
    if (!strategies.data?.length) return
    setBtLoading(true)
    const fetches = strategies.data.map((s) =>
      getBacktest(s.id).then((bt) => ({ id: s.id, bt })).catch(() => null),
    )
    Promise.all(fetches).then((results) => {
      const map: Record<number, BacktestResult> = {}
      for (const r of results) {
        if (r) map[r.id] = r.bt
      }
      setBacktests(map)
      setBtLoading(false)
    })
  }, [strategies.data])

  if (strategies.loading) return <Loading />
  if (strategies.error) return <ErrorDisplay message={strategies.error} onRetry={strategies.reload} />

  const allStrategies = strategies.data || []
  const tabs = [...new Set(allStrategies.map((s) => s.category))]
  const filtered = allStrategies.filter((s) => s.category === activeTab)

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">策略中心</h2>

      {/* Category tabs */}
      <div className="flex gap-2">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm rounded-lg transition-colors ${
              activeTab === tab
                ? 'bg-primary text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Strategy cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((s) => (
          <StrategyCard key={s.id} strategy={s} backtest={backtests[s.id]} loading={btLoading} />
        ))}
      </div>
    </div>
  )
}

// Mapping of strategy_type to similar classic strategy labels
const SIMILAR_STRATEGY_MAP: Record<string, string> = {
  all_weather_cn: '与经典策略A4(大类资产配置)逻辑相似',
  huabao_grid: '与经典策略A3(网格交易)逻辑相似',
}

function StrategyCard({
  strategy,
  backtest,
  loading,
}: {
  strategy: StrategyItem
  backtest?: BacktestResult
  loading: boolean
}) {
  const similarLabel = SIMILAR_STRATEGY_MAP[strategy.strategy_type]

  return (
    <Link to={`/strategy/${strategy.id}`}>
      <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
        <div className="space-y-3">
          <div>
            <h3 className="font-medium text-gray-900">{strategy.name}</h3>
            <span className="text-xs text-gray-400">{strategy.strategy_type}</span>
          </div>
          {similarLabel && (
            <span className="inline-block text-xs px-2 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200">
              {similarLabel}
            </span>
          )}
          <p className="text-xs text-gray-500 line-clamp-2">{strategy.description}</p>
          {loading ? (
            <div className="text-xs text-gray-400">加载中...</div>
          ) : backtest ? (
            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-gray-100">
              <div>
                <div className="text-xs text-gray-400">年化收益</div>
                <div className={`text-sm font-semibold ${(backtest.annual_return ?? 0) >= 0 ? 'text-rise' : 'text-fall'}`}>
                  {formatPercent(backtest.annual_return)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">最大回撤</div>
                <div className="text-sm font-semibold text-fall">
                  {formatPercent(backtest.max_drawdown)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">夏普比率</div>
                <div className="text-sm font-semibold text-gray-900">
                  {formatNumber(backtest.sharpe_ratio)}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-gray-400">暂无回测数据</div>
          )}
        </div>
      </Card>
    </Link>
  )
}
