import ReactECharts from 'echarts-for-react'
import type { EtfDailyData } from '@/types/api'

interface KLineChartProps {
  data: EtfDailyData[]
  height?: number
}

export default function KLineChart({ data, height = 500 }: KLineChartProps) {
  if (!data.length) {
    return <div className="text-center text-gray-400 py-10">暂无K线数据</div>
  }

  const dates = data.map((d) => d.trade_date)
  const ohlc = data.map((d) => [d.open, d.close, d.low, d.high])
  const volumes = data.map((d) => d.volume ?? 0)

  // Calculate MA
  const calcMA = (period: number): (number | null)[] => {
    const result: (number | null)[] = []
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1 || data[i].close == null) {
        result.push(null)
        continue
      }
      let sum = 0
      let count = 0
      for (let j = i - period + 1; j <= i; j++) {
        if (data[j].close != null) {
          sum += data[j].close!
          count++
        }
      }
      result.push(count > 0 ? sum / count : null)
    }
    return result
  }

  const ma5 = calcMA(5)
  const ma10 = calcMA(10)
  const ma20 = calcMA(20)

  // Color volumes: green if close < open, red otherwise
  const volumeColors = data.map((d) => {
    if (d.close == null || d.open == null) return '#999'
    return d.close >= d.open ? '#ef4444' : '#22c55e'
  })

  const option = {
    animation: false,
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'cross' as const },
    },
    grid: [
      { left: '8%', right: '3%', top: '5%', height: '55%' },
      { left: '8%', right: '3%', top: '68%', height: '20%' },
    ],
    xAxis: [
      {
        type: 'category' as const,
        data: dates,
        axisLine: { lineStyle: { color: '#ddd' } },
        axisLabel: { fontSize: 10, color: '#999' },
        gridIndex: 0,
      },
      {
        type: 'category' as const,
        data: dates,
        gridIndex: 1,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
      },
    ],
    yAxis: [
      {
        type: 'value' as const,
        scale: true,
        splitLine: { lineStyle: { color: '#f0f0f0' } },
        axisLabel: { fontSize: 10, color: '#999' },
        gridIndex: 0,
      },
      {
        type: 'value' as const,
        scale: true,
        gridIndex: 1,
        splitLine: { show: false },
        axisLabel: { show: false },
      },
    ],
    dataZoom: [
      {
        type: 'inside' as const,
        xAxisIndex: [0, 1],
        start: Math.max(0, 100 - (120 / data.length) * 100),
        end: 100,
      },
      {
        type: 'slider' as const,
        xAxisIndex: [0, 1],
        top: '92%',
        height: 20,
        start: Math.max(0, 100 - (120 / data.length) * 100),
        end: 100,
      },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick' as const,
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e',
        },
      },
      {
        name: 'MA5',
        type: 'line' as const,
        data: ma5,
        smooth: true,
        lineStyle: { width: 1 },
        symbol: 'none',
        xAxisIndex: 0,
        yAxisIndex: 0,
      },
      {
        name: 'MA10',
        type: 'line' as const,
        data: ma10,
        smooth: true,
        lineStyle: { width: 1 },
        symbol: 'none',
        xAxisIndex: 0,
        yAxisIndex: 0,
      },
      {
        name: 'MA20',
        type: 'line' as const,
        data: ma20,
        smooth: true,
        lineStyle: { width: 1 },
        symbol: 'none',
        xAxisIndex: 0,
        yAxisIndex: 0,
      },
      {
        name: '成交量',
        type: 'bar' as const,
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: volumeColors[i] },
        })),
        xAxisIndex: 1,
        yAxisIndex: 1,
      },
    ],
  }

  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />
}
