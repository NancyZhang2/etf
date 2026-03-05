interface PaginationProps {
  current: number
  total: number
  pageSize: number
  onChange: (page: number) => void
}

export default function Pagination({ current, total, pageSize, onChange }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize)
  if (totalPages <= 1) return null

  const pages: number[] = []
  const start = Math.max(1, current - 2)
  const end = Math.min(totalPages, current + 2)
  for (let i = start; i <= end; i++) pages.push(i)

  return (
    <div className="flex items-center justify-center gap-1 mt-4">
      <button
        disabled={current <= 1}
        onClick={() => onChange(current - 1)}
        className="px-3 py-1.5 text-sm rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
      >
        上一页
      </button>
      {start > 1 && (
        <>
          <button onClick={() => onChange(1)} className="px-3 py-1.5 text-sm rounded border border-gray-200 hover:bg-gray-50">1</button>
          {start > 2 && <span className="px-1 text-gray-400">...</span>}
        </>
      )}
      {pages.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`px-3 py-1.5 text-sm rounded border ${
            p === current
              ? 'bg-primary text-white border-primary'
              : 'border-gray-200 hover:bg-gray-50'
          }`}
        >
          {p}
        </button>
      ))}
      {end < totalPages && (
        <>
          {end < totalPages - 1 && <span className="px-1 text-gray-400">...</span>}
          <button onClick={() => onChange(totalPages)} className="px-3 py-1.5 text-sm rounded border border-gray-200 hover:bg-gray-50">{totalPages}</button>
        </>
      )}
      <button
        disabled={current >= totalPages}
        onClick={() => onChange(current + 1)}
        className="px-3 py-1.5 text-sm rounded border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
      >
        下一页
      </button>
    </div>
  )
}
