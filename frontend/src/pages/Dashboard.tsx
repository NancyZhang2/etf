import { useApi } from '@/hooks/useApi'
import { getSignalsLatest } from '@/services/quantApi'
import { getResearchReports } from '@/services/researchApi'
import { getDataStatus } from '@/services/dataApi'
import Card from '@/components/common/Card'
import SignalBadge from '@/components/common/SignalBadge'
import Loading from '@/components/common/Loading'
import ErrorDisplay from '@/components/common/ErrorDisplay'
import { formatDate, formatVolume } from '@/utils/format'
import { Link } from 'react-router-dom'

export default function Dashboard() {
  const signals = useApi(() => getSignalsLatest())
  const reports = useApi(() => getResearchReports({ page: 1, page_size: 5 }))
  const status = useApi(() => getDataStatus())

  const loading = signals.loading || reports.loading || status.loading
  const error = signals.error || reports.error || status.error

  if (loading) return <Loading />
  if (error) return <ErrorDisplay message={error} onRetry={() => { signals.reload(); reports.reload(); status.reload() }} />

  const signalData = signals.data || []
  const buyCount = signalData.filter((s) => s.signal === 'BUY').length
  const sellCount = signalData.filter((s) => s.signal === 'SELL').length
  const holdCount = signalData.filter((s) => s.signal === 'HOLD').length

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">首页</h2>

      {/* Signal summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-rise/5 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-rise">{buyCount}</div>
          <div className="text-xs text-gray-500 mt-1">买入信号</div>
        </div>
        <div className="bg-fall/5 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-fall">{sellCount}</div>
          <div className="text-xs text-gray-500 mt-1">卖出信号</div>
        </div>
        <div className="bg-gray-50 rounded-xl p-4 text-center">
          <div className="text-2xl font-bold text-gray-600">{holdCount}</div>
          <div className="text-xs text-gray-500 mt-1">持有信号</div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Today's signals */}
        <Card title="最新交易信号" extra={<Link to="/signals" className="text-primary text-xs">查看全部</Link>}>
          {signalData.length === 0 ? (
            <div className="text-gray-400 text-sm text-center py-4">暂无信号</div>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {signalData.slice(0, 15).map((s, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <SignalBadge signal={s.signal} />
                    <Link to={`/etf/${s.etf_code}`} className="text-sm hover:text-primary">
                      {s.etf_code}
                    </Link>
                    <span className="text-xs text-gray-400">{s.etf_name}</span>
                  </div>
                  <div className="text-xs text-gray-400">{s.strategy_name}</div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Latest research */}
        <Card title="最新研报" extra={<Link to="/research" className="text-primary text-xs">查看全部</Link>}>
          {!reports.data?.items?.length ? (
            <div className="text-gray-400 text-sm text-center py-4">暂无研报</div>
          ) : (
            <div className="space-y-3">
              {reports.data.items.map((r) => (
                <Link key={r.id} to={`/research/${r.id}`} className="block hover:bg-gray-50 rounded-lg p-2 -mx-2 transition-colors">
                  <div className="text-sm font-medium text-gray-900 line-clamp-1">{r.title}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-400">{r.source}</span>
                    <span className="text-xs text-gray-300">|</span>
                    <span className="text-xs text-gray-400">{formatDate(r.report_date)}</span>
                  </div>
                  {r.summary && (
                    <div className="text-xs text-gray-500 mt-1 line-clamp-2">{r.summary}</div>
                  )}
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* System status */}
      {status.data && (
        <Card title="系统状态">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <div className="text-lg font-semibold text-gray-900">{status.data.etf_count}</div>
              <div className="text-xs text-gray-500">ETF数量</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-gray-900">{formatVolume(status.data.record_count)}</div>
              <div className="text-xs text-gray-500">行情记录</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-gray-900">{formatDate(status.data.last_sync)}</div>
              <div className="text-xs text-gray-500">最后同步</div>
            </div>
            <div>
              <div className={`text-lg font-semibold ${status.data.status === 'ok' ? 'text-fall' : 'text-rise'}`}>
                {status.data.status === 'ok' ? '正常' : status.data.status}
              </div>
              <div className="text-xs text-gray-500">系统状态</div>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
