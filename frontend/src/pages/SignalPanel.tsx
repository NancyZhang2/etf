import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '@/hooks/useApi'
import { getSignalsLatest, getSignalHistory, getStrategies } from '@/services/quantApi'
import Loading from '@/components/common/Loading'
import ErrorDisplay from '@/components/common/ErrorDisplay'
import Card from '@/components/common/Card'
import SignalBadge from '@/components/common/SignalBadge'
import Pagination from '@/components/common/Pagination'
import { formatDate } from '@/utils/format'

export default function SignalPanel() {
  const [tab, setTab] = useState<'today' | 'history'>('today')

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">信号面板</h2>

      <div className="flex gap-2">
        <button
          onClick={() => setTab('today')}
          className={`px-4 py-2 text-sm rounded-lg ${tab === 'today' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}`}
        >
          最新信号
        </button>
        <button
          onClick={() => setTab('history')}
          className={`px-4 py-2 text-sm rounded-lg ${tab === 'history' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}`}
        >
          历史信号
        </button>
      </div>

      {tab === 'today' ? <TodaySignals /> : <HistorySignals />}
    </div>
  )
}

function TodaySignals() {
  const { data, loading, error, reload } = useApi(() => getSignalsLatest())

  if (loading) return <Loading />
  if (error) return <ErrorDisplay message={error} onRetry={reload} />

  const signals = data || []
  const groups = {
    BUY: signals.filter((s) => s.signal === 'BUY'),
    SELL: signals.filter((s) => s.signal === 'SELL'),
    HOLD: signals.filter((s) => s.signal === 'HOLD'),
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex gap-4 text-sm">
        <span className="text-rise font-medium">BUY: {groups.BUY.length}</span>
        <span className="text-fall font-medium">SELL: {groups.SELL.length}</span>
        <span className="text-gray-500">HOLD: {groups.HOLD.length}</span>
      </div>

      {(['BUY', 'SELL', 'HOLD'] as const).map((type) => {
        const items = groups[type]
        if (!items.length) return null
        return (
          <Card key={type} title={`${type} 信号 (${items.length})`}>
            <div className="space-y-2">
              {items.map((s, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <SignalBadge signal={s.signal} />
                    <Link to={`/etf/${s.etf_code}`} className="text-sm text-primary font-mono">{s.etf_code}</Link>
                    <span className="text-xs text-gray-400">{s.etf_name}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">{s.strategy_name}</span>
                    <span className="text-xs text-gray-300">{formatDate(s.signal_date)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )
      })}

      {signals.length === 0 && (
        <div className="text-center text-gray-400 py-10">暂无信号数据</div>
      )}
    </div>
  )
}

function HistorySignals() {
  const [strategyId, setStrategyId] = useState<number | undefined>()
  const [etfCode, setEtfCode] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const strategies = useApi(() => getStrategies())
  const history = useApi(
    () => getSignalHistory({
      strategy_id: strategyId,
      etf_code: etfCode || undefined,
    }),
    [strategyId, etfCode],
  )

  // Client-side pagination
  const allItems = history.data || []
  const paged = useMemo(() => {
    const start = (page - 1) * pageSize
    return allItems.slice(start, start + pageSize)
  }, [allItems, page])

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary"
          value={strategyId ?? ''}
          onChange={(e) => { setStrategyId(e.target.value ? Number(e.target.value) : undefined); setPage(1) }}
        >
          <option value="">全部策略</option>
          {(strategies.data || []).map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="ETF代码"
          value={etfCode}
          onChange={(e) => { setEtfCode(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary w-32"
        />
      </div>

      {history.loading ? (
        <Loading />
      ) : history.error ? (
        <ErrorDisplay message={history.error} onRetry={history.reload} />
      ) : (
        <>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left bg-gray-50">
                    <th className="px-3 py-2 font-medium text-gray-500">日期</th>
                    <th className="px-3 py-2 font-medium text-gray-500">信号</th>
                    <th className="px-3 py-2 font-medium text-gray-500">原因</th>
                  </tr>
                </thead>
                <tbody>
                  {paged.length === 0 ? (
                    <tr><td colSpan={3} className="text-center py-8 text-gray-400">暂无数据</td></tr>
                  ) : (
                    paged.map((s, i) => (
                      <tr key={i} className="border-t border-gray-50">
                        <td className="px-3 py-2 text-gray-500">{formatDate(s.signal_date)}</td>
                        <td className="px-3 py-2"><SignalBadge signal={s.signal} /></td>
                        <td className="px-3 py-2 text-xs text-gray-500 max-w-md truncate">{s.reason || '--'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>
          <Pagination current={page} total={allItems.length} pageSize={pageSize} onChange={setPage} />
        </>
      )}
    </div>
  )
}
