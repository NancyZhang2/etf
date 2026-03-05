import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '@/hooks/useApi'
import { getResearchReports } from '@/services/researchApi'
import Loading from '@/components/common/Loading'
import ErrorDisplay from '@/components/common/ErrorDisplay'
import Card from '@/components/common/Card'
import Pagination from '@/components/common/Pagination'
import { formatDate } from '@/utils/format'

export default function ResearchList() {
  const [page, setPage] = useState(1)
  const [etfCode, setEtfCode] = useState('')
  const pageSize = 15

  const { data, loading, error, reload } = useApi(
    () => getResearchReports({ etf_code: etfCode || undefined, page, page_size: pageSize }),
    [page, etfCode],
  )

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">研报中心</h2>

      {/* Filter */}
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="ETF代码筛选"
          value={etfCode}
          onChange={(e) => { setEtfCode(e.target.value); setPage(1) }}
          className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-primary w-40"
        />
      </div>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorDisplay message={error} onRetry={reload} />
      ) : (
        <>
          <div className="text-xs text-gray-400">共 {data?.total ?? 0} 篇研报</div>

          <div className="space-y-3">
            {(!data?.items?.length) ? (
              <div className="text-center text-gray-400 py-10">暂无研报</div>
            ) : (
              data.items.map((r) => (
                <Link key={r.id} to={`/research/${r.id}`}>
                  <Card className="hover:shadow-md transition-shadow cursor-pointer">
                    <div>
                      <div className="flex items-start justify-between gap-4">
                        <h3 className="text-sm font-medium text-gray-900 line-clamp-1 flex-1">{r.title}</h3>
                        {r.etf_code && (
                          <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded shrink-0">{r.etf_code}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-400">{r.source}</span>
                        <span className="text-xs text-gray-300">|</span>
                        <span className="text-xs text-gray-400">{formatDate(r.report_date)}</span>
                      </div>
                      {r.summary && (
                        <p className="text-xs text-gray-500 mt-2 line-clamp-2">{r.summary}</p>
                      )}
                    </div>
                  </Card>
                </Link>
              ))
            )}
          </div>

          <Pagination current={page} total={data?.total ?? 0} pageSize={pageSize} onChange={setPage} />
        </>
      )}
    </div>
  )
}
