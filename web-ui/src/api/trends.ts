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

export interface TrendKeyword {
  id: number
  keyword: string
  category: string
  enabled: boolean
  notes: string
  created_at: string
  updated_at: string
}

export async function getDailyReportConfig(): Promise<TrendDailyReportConfig> {
  return await http('/api/trends/daily-report/config')
}

export async function getTrendKeywords(params: {
  include_disabled?: boolean
} = {}): Promise<TrendKeyword[]> {
  const response = await http('/api/trends/keywords', { params })
  return response.items || []
}

export async function createTrendKeyword(payload: {
  keyword: string
  category?: string
  notes?: string
  enabled?: boolean
}): Promise<TrendKeyword> {
  const response = await http('/api/trends/keywords', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return response.item
}

export async function deleteTrendKeyword(keywordId: number): Promise<void> {
  await http(`/api/trends/keywords/${keywordId}`, {
    method: 'DELETE',
  })
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
  refresh_snapshots?: boolean
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

export async function refreshTrendSnapshots(payload: {
  limit_per_keyword: number
}): Promise<{
  message: string
  created_count: number
  skipped_count: number
  items: unknown[]
  skipped: Array<{ keyword_id: number; keyword: string }>
}> {
  return await http('/api/trends/snapshots/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function syncTrendMonitorTasks(payload: {
  cron: string
  max_pages: number
  personal_only: boolean
  free_shipping: boolean
  new_publish_option?: string | null
  update_existing: boolean
}): Promise<{
  message: string
  created_count: number
  updated_count: number
  existing_count: number
  skipped_count: number
  items: Array<{ keyword: string; task_id: number; task_name: string; action: string }>
}> {
  return await http('/api/trends/monitor-tasks/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
