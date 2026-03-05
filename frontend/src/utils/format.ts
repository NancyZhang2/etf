import dayjs from 'dayjs'

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return '--'
  return `${(value * 100).toFixed(2)}%`
}

export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '--'
  return value.toFixed(decimals)
}

export function formatVolume(value: number | null | undefined): string {
  if (value == null) return '--'
  if (value >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
  if (value >= 1e4) return `${(value / 1e4).toFixed(2)}万`
  return value.toFixed(0)
}

export function formatDate(value: string | null | undefined, fmt = 'YYYY-MM-DD'): string {
  if (!value) return '--'
  return dayjs(value).format(fmt)
}

export function formatAmount(value: number | null | undefined): string {
  if (value == null) return '--'
  if (value >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
  if (value >= 1e4) return `${(value / 1e4).toFixed(2)}万`
  return value.toFixed(2)
}
