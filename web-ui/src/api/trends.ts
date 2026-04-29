import { http } from '@/lib/http'

export interface TrendDailyReportConfig {
  enabled: boolean
  cron: string
  bark_configured: boolean
  ai_configured: boolean
}

export interface TrendDailyReportItem {
  snapshot_id: number
  keyword: string
  rank: string
  should_push: boolean
  why: string
  sell_angle: string
  advantages: string[]
  risks: string[]
  next_action: string
}

export interface TrendDailyReport {
  id: number
  report_date: string
  status: string
  candidate_snapshot_ids: number[]
  ai_review: {
    daily_summary?: string
    items?: TrendDailyReportItem[]
  }
  push_title: string
  push_body: string
  push_channel: string
  push_status: string
  error_message: string
  created_at: string
  sent_at?: string | null
}

export async function getDailyReportConfig(): Promise<TrendDailyReportConfig> {
  return await http('/api/trends/daily-report/config')
}

export async function getLatestDailyReport(): Promise<TrendDailyReport | null> {
  try {
    const response = await http('/api/trends/daily-report/latest')
    return response.item
  } catch (error) {
    if ((error as Error).message.includes('暂无闲鱼机会日报')) {
      return null
    }
    throw error
  }
}

export async function runDailyReport(payload: {
  candidate_limit: number
  push: boolean
}): Promise<TrendDailyReport> {
  const response = await http('/api/trends/daily-report/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return response.item
}

export async function sendDailyReportTest(payload: {
  title: string
  body: string
}): Promise<{ channel: string; success: boolean; message: string }> {
  const response = await http('/api/trends/daily-report/send-test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return response.result
}
