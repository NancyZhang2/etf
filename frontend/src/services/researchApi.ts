import api from './api'
import type {
  ResearchReportList,
  ResearchReportDetail,
  ResearchFramework,
  SentimentStats,
  MacroConsensus,
} from '@/types/api'

export function getResearchReports(params: {
  etf_code?: string
  page?: number
  page_size?: number
}): Promise<ResearchReportList> {
  return api.get('/research/reports', { params })
}

export function getResearchReportDetail(id: number): Promise<ResearchReportDetail> {
  return api.get(`/research/reports/${id}`)
}

export function getResearchFramework(etfCode: string): Promise<ResearchFramework> {
  return api.get(`/research/${etfCode}/framework`)
}

export function getResearchSentiment(etfCode: string): Promise<SentimentStats> {
  return api.get(`/research/${etfCode}/sentiment`)
}

export function getResearchMacro(): Promise<MacroConsensus> {
  return api.get('/research/macro')
}
