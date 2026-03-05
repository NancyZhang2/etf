import { useParams, Link } from 'react-router-dom'
import { useApi } from '@/hooks/useApi'
import { getEtfInfo, getEtfDaily } from '@/services/dataApi'
import { getSignalHistory } from '@/services/quantApi'
import { getResearchReports } from '@/services/researchApi'
import Loading from '@/components/common/Loading'
import ErrorDisplay from '@/components/common/ErrorDisplay'
import Card from '@/components/common/Card'
import SignalBadge from '@/components/common/SignalBadge'
import KLineChart from '@/components/charts/KLineChart'
import { formatDate } from '@/utils/format'
import dayjs from 'dayjs'

export default function EtfDetail() {
  const { code } = useParams<{ code: string }>()

  const info = useApi(() => getEtfInfo(code!), [code])
  const sixMonthsAgo = dayjs().subtract(6, 'month').format('YYYY-MM-DD')
  const daily = useApi(() => getEtfDaily(code!, sixMonthsAgo), [code])
  const signals = useApi(() => getSignalHistory({ etf_code: code }), [code])
  const reports = useApi(() => getResearchReports({ etf_code: code, page_size: 5 }), [code])

  if (info.loading) return <Loading />
  if (info.error) return <ErrorDisplay message={info.error} onRetry={info.reload} />
  if (!info.data) return <ErrorDisplay message="ETF不存在" />

  const e = info.data

  return (
    <div className="space-y-6">
      <div>
        <Link to="/etf" className="text-sm text-gray-400 hover:text-primary">&larr; 返回ETF列表</Link>
        <h2 className="text-xl font-bold mt-2">{e.name} <span className="text-base font-normal text-gray-400">{e.code}</span></h2>
      </div>

      {/* Basic info */}
      <Card title="基本信息">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
          <div>
            <span className="text-gray-400 text-xs block">代码</span>
            <span className="font-mono">{e.code}</span>
          </div>
          <div>
            <span className="text-gray-400 text-xs block">名称</span>
            <span>{e.name}</span>
          </div>
          <div>
            <span className="text-gray-400 text-xs block">分类</span>
            <span>{e.category}</span>
          </div>
          <div>
            <span className="text-gray-400 text-xs block">交易所</span>
            <span>{e.exchange}</span>
          </div>
          <div>
            <span className="text-gray-400 text-xs block">上市日期</span>
            <span>{formatDate(e.list_date)}</span>
          </div>
        </div>
      </Card>

      {/* K-line chart */}
      <Card title="K线图（近6个月）">
        {daily.loading ? (
          <Loading />
        ) : daily.error ? (
          <ErrorDisplay message={daily.error} onRetry={daily.reload} />
        ) : (
          <KLineChart data={daily.data || []} />
        )}
      </Card>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Related signals */}
        <Card title="关联信号">
          {signals.loading ? (
            <Loading />
          ) : !signals.data?.length ? (
            <div className="text-gray-400 text-sm text-center py-4">暂无信号</div>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {signals.data.slice(0, 20).map((s, i) => (
                <div key={i} className="flex items-center justify-between py-1 border-b border-gray-50 last:border-0">
                  <SignalBadge signal={s.signal} />
                  <span className="text-xs text-gray-400">{formatDate(s.signal_date)}</span>
                  <span className="text-xs text-gray-500 truncate max-w-[200px]">{s.reason || '--'}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Related research */}
        <Card title="关联研报">
          {reports.loading ? (
            <Loading />
          ) : !reports.data?.items?.length ? (
            <div className="text-gray-400 text-sm text-center py-4">暂无研报</div>
          ) : (
            <div className="space-y-2">
              {reports.data.items.map((r) => (
                <Link
                  key={r.id}
                  to={`/research/${r.id}`}
                  className="block hover:bg-gray-50 rounded p-2 -mx-2 transition-colors"
                >
                  <div className="text-sm line-clamp-1">{r.title}</div>
                  <div className="text-xs text-gray-400 mt-0.5">{r.source} | {formatDate(r.report_date)}</div>
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
