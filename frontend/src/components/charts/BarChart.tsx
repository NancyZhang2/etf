import ReactECharts from 'echarts-for-react'

interface BarChartProps {
  labels: string[]
  values: (number | null)[]
  height?: number
  yAxisLabel?: string
  /** If true, positive bars are red, negative are green (Chinese market convention) */
  risefall?: boolean
}

export default function BarChart({
  labels,
  values,
  height = 300,
  yAxisLabel,
  risefall = true,
}: BarChartProps) {
  if (!labels.length) {
    return <div className="text-center text-gray-400 py-10">暂无数据</div>
  }

  const coloredData = values.map((v) => {
    if (v == null) return { value: 0 }
    if (!risefall) return { value: v }
    return {
      value: v,
      itemStyle: { color: v >= 0 ? '#ef4444' : '#22c55e' },
    }
  })

  const option = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: Array<{ name: string; value: number }>) => {
        const p = params[0]
        return `${p.name}: ${(p.value * 100).toFixed(2)}%`
      },
    },
    grid: {
      left: '10%',
      right: '5%',
      top: '10%',
      bottom: '12%',
    },
    xAxis: {
      type: 'category' as const,
      data: labels,
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value' as const,
      name: yAxisLabel,
      axisLabel: {
        fontSize: 10,
        formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
      },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series: [
      {
        type: 'bar' as const,
        data: coloredData,
        barMaxWidth: 40,
      },
    ],
  }

  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />
}
