import api from './api'
import type {
  EtfBasicInfo,
  EtfCategory,
  EtfDailyData,
  DataStatus,
  TradingCalendarDay,
} from '@/types/api'

export function getEtfList(category?: string): Promise<EtfBasicInfo[]> {
  return api.get('/etf/list', { params: category ? { category } : {} })
}

export function getEtfCategories(): Promise<EtfCategory[]> {
  return api.get('/etf/list/categories')
}

export function getEtfInfo(code: string): Promise<EtfBasicInfo> {
  return api.get(`/etf/${code}/info`)
}

export function getEtfDaily(
  code: string,
  startDate?: string,
  endDate?: string,
): Promise<EtfDailyData[]> {
  return api.get(`/etf/${code}/daily`, {
    params: { start_date: startDate, end_date: endDate },
  })
}

export function getEtfLatest(code: string): Promise<EtfDailyData> {
  return api.get(`/etf/${code}/latest`)
}

export function getEtfBatchDaily(
  codes: string[],
  startDate?: string,
  endDate?: string,
): Promise<Record<string, EtfDailyData[]>> {
  return api.get('/etf/batch/daily', {
    params: { codes: codes.join(','), start_date: startDate, end_date: endDate },
  })
}

export function triggerDataSync(): Promise<{ message: string }> {
  return api.post('/data/sync')
}

export function getDataStatus(): Promise<DataStatus> {
  return api.get('/data/status')
}

export function getTradingCalendar(year?: number): Promise<TradingCalendarDay[]> {
  return api.get('/data/calendar', { params: year ? { year } : {} })
}
