import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '@/hooks/useApi'
import { getEtfList, getEtfCategories } from '@/services/dataApi'
import Loading from '@/components/common/Loading'
import ErrorDisplay from '@/components/common/ErrorDisplay'
import SearchInput from '@/components/common/SearchInput'

export default function EtfList() {
  const [activeCategory, setActiveCategory] = useState<string>('')
  const [searchTerm, setSearchTerm] = useState('')

  const etfs = useApi(() => getEtfList())
  const categories = useApi(() => getEtfCategories())

  if (etfs.loading || categories.loading) return <Loading />
  if (etfs.error) return <ErrorDisplay message={etfs.error} onRetry={etfs.reload} />

  const allEtfs = etfs.data || []
  const cats = categories.data || []

  // Client-side filtering
  const filtered = useMemo(() => {
    let result = allEtfs
    if (activeCategory) {
      result = result.filter((e) => e.category === activeCategory)
    }
    if (searchTerm) {
      const term = searchTerm.toLowerCase()
      result = result.filter(
        (e) =>
          e.code.toLowerCase().includes(term) ||
          e.name.toLowerCase().includes(term),
      )
    }
    return result
  }, [allEtfs, activeCategory, searchTerm])

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">ETF列表</h2>

      {/* Search */}
      <div className="max-w-md">
        <SearchInput placeholder="搜索代码或名称..." onSearch={setSearchTerm} />
      </div>

      {/* Category tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveCategory('')}
          className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
            !activeCategory
              ? 'bg-primary text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          全部 ({allEtfs.length})
        </button>
        {cats.map((c) => (
          <button
            key={c.category}
            onClick={() => setActiveCategory(c.category)}
            className={`px-3 py-1.5 text-sm rounded-full transition-colors ${
              activeCategory === c.category
                ? 'bg-primary text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {c.category} ({c.count})
          </button>
        ))}
      </div>

      {/* Results count */}
      <div className="text-xs text-gray-400">共 {filtered.length} 只ETF</div>

      {/* ETF list */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="px-4 py-3 font-medium text-gray-500">代码</th>
              <th className="px-4 py-3 font-medium text-gray-500">名称</th>
              <th className="px-4 py-3 font-medium text-gray-500 hidden md:table-cell">分类</th>
              <th className="px-4 py-3 font-medium text-gray-500 hidden md:table-cell">交易所</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={4} className="text-center py-8 text-gray-400">
                  {searchTerm ? '无匹配结果' : '暂无数据'}
                </td>
              </tr>
            ) : (
              filtered.map((e) => (
                <tr key={e.code} className="border-t border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link to={`/etf/${e.code}`} className="text-primary font-mono">
                      {e.code}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/etf/${e.code}`} className="hover:text-primary">
                      {e.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell">{e.category}</td>
                  <td className="px-4 py-3 text-gray-500 hidden md:table-cell">{e.exchange}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
