import { useParams, Link } from 'react-router-dom'
import { useApi } from '@/hooks/useApi'
import { getResearchReportDetail } from '@/services/researchApi'
import Loading from '@/components/common/Loading'
import ErrorDisplay from '@/components/common/ErrorDisplay'
import Card from '@/components/common/Card'
import { formatDate } from '@/utils/format'

export default function ResearchDetail() {
  const { id } = useParams<{ id: string }>()
  const reportId = Number(id)

  const { data, loading, error, reload } = useApi(
    () => getResearchReportDetail(reportId),
    [reportId],
  )

  if (loading) return <Loading />
  if (error) return <ErrorDisplay message={error} onRetry={reload} />
  if (!data) return <ErrorDisplay message="研报不存在" />

  const r = data
  const analysis = r.analysis

  return (
    <div className="space-y-6">
      <div>
        <Link to="/research" className="text-sm text-gray-400 hover:text-primary">&larr; 返回研报列表</Link>
        <h2 className="text-xl font-bold mt-2">{r.title}</h2>
        <div className="flex items-center gap-3 mt-2 text-sm text-gray-400">
          <span>{r.source}</span>
          <span>|</span>
          <span>{formatDate(r.report_date)}</span>
          {r.etf_code && (
            <>
              <span>|</span>
              <Link to={`/etf/${r.etf_code}`} className="text-primary">{r.etf_code}</Link>
            </>
          )}
        </div>
      </div>

      {/* Original content */}
      {r.content && (
        <Card title="研报原文">
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
            {r.content}
          </div>
        </Card>
      )}

      {/* AI Analysis */}
      {analysis && (
        <div className="space-y-4">
          <h3 className="text-lg font-bold">AI分析</h3>

          {/* Summary */}
          {analysis.summary && (
            <Card title="摘要">
              <p className="text-sm text-gray-700">{analysis.summary}</p>
            </Card>
          )}

          {/* Sentiment + Confidence */}
          {(analysis.sentiment || analysis.confidence != null) && (
            <Card title="情绪判断">
              <div className="flex items-center gap-4">
                {analysis.sentiment && (
                  <span className={`text-sm font-medium px-3 py-1 rounded ${
                    analysis.sentiment === 'bullish' ? 'bg-rise/10 text-rise' :
                    analysis.sentiment === 'bearish' ? 'bg-fall/10 text-fall' :
                    'bg-gray-100 text-gray-600'
                  }`}>
                    {analysis.sentiment === 'bullish' ? '看多' :
                     analysis.sentiment === 'bearish' ? '看空' : '中性'}
                  </span>
                )}
                {analysis.confidence != null && (
                  <span className="text-sm text-gray-500">
                    置信度: {(analysis.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            </Card>
          )}

          {/* Macro view */}
          {analysis.macro_view && (
            <Card title="宏观观点">
              <div className="space-y-3">
                {analysis.macro_view.economy && (
                  <div>
                    <span className="text-xs font-medium text-gray-400">经济</span>
                    <p className="text-sm text-gray-700 mt-0.5">{analysis.macro_view.economy}</p>
                  </div>
                )}
                {analysis.macro_view.liquidity && (
                  <div>
                    <span className="text-xs font-medium text-gray-400">流动性</span>
                    <p className="text-sm text-gray-700 mt-0.5">{analysis.macro_view.liquidity}</p>
                  </div>
                )}
                {analysis.macro_view.policy && (
                  <div>
                    <span className="text-xs font-medium text-gray-400">政策</span>
                    <p className="text-sm text-gray-700 mt-0.5">{analysis.macro_view.policy}</p>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Risk factors */}
          {analysis.risk_factors?.length ? (
            <Card title="风险因素">
              <ul className="space-y-1">
                {analysis.risk_factors.map((risk, i) => (
                  <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                    <span className="text-rise mt-0.5">!</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {/* Key points */}
          {analysis.key_points?.length ? (
            <Card title="关键要点">
              <ul className="space-y-1">
                {analysis.key_points.map((point, i) => (
                  <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                    <span className="text-primary mt-0.5">-</span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {/* ETF relevance */}
          {analysis.etf_relevance && (
            <Card title="ETF关联度">
              <p className="text-sm text-gray-700">{analysis.etf_relevance}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
