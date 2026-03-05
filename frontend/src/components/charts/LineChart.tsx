import ReactECharts from 'echarts-for-react'

interface Series {
  name: string
  data: (number | null)[]
  color?: string
  areaStyle?: boolean
}

interface LineChartProps {
  dates: string[]
  series: Series[]
  height?: number
  yAxisLabel?: string
}

export default function LineChart({ dates, series, height = 350, yAxisLabel }: LineChartProps) {
  if (!dates.length) {
    return <div className="text-center text-gray-400 py-10">暂无数据</div>
  }

  const option = {
    tooltip: {
      trigger: 'axis' as const,
    },
    legend: {
      data: series.map((s) => s.name),
      bottom: 0,
      textStyle: { fontSize: 11 },
    },
    grid: {
      left: '8%',
      right: '3%',
      top: '8%',
      bottom: '15%',
    },
    xAxis: {
      type: 'category' as const,
      data: dates,
      axisLabel: { fontSize: 10, color: '#999' },
      axisLine: { lineStyle: { color: '#ddd' } },
    },
    yAxis: {
      type: 'value' as const,
      scale: true,
      name: yAxisLabel,
      nameTextStyle: { fontSize: 10, color: '#999' },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
      axisLabel: { fontSize: 10, color: '#999' },
    },
    dataZoom: [
      {
        type: 'inside' as const,
        start: 0,
        end: 100,
      },
    ],
    series: series.map((s) => ({
      name: s.name,
      type: 'line' as const,
      data: s.data,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.5, color: s.color },
      itemStyle: { color: s.color },
      ...(s.areaStyle
        ? { areaStyle: { opacity: 0.15, color: s.color } }
        : {}),
    })),
  }

  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />
}
