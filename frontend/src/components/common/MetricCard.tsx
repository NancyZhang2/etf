interface MetricCardProps {
  label: string
  value: string
  sub?: string
  color?: 'rise' | 'fall' | 'default'
}

export default function MetricCard({ label, value, sub, color = 'default' }: MetricCardProps) {
  const colorClass =
    color === 'rise'
      ? 'text-rise'
      : color === 'fall'
        ? 'text-fall'
        : 'text-gray-900'

  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${colorClass}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}
