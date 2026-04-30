<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Bell,
  CalendarClock,
  CheckCircle2,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  TriangleAlert,
  WandSparkles,
} from 'lucide-vue-next'
import {
  createTrendKeyword,
  deleteTrendKeyword,
  getDailyReportConfig,
  getLatestDailyReport,
  getTrendKeywords,
  refreshTrendSnapshots,
  runDailyReport,
  sendDailyReportTest,
  syncTrendMonitorTasks,
  type TrendDailyReport,
  type TrendDailyReportConfig,
  type TrendDailyReportItem,
  type TrendKeyword,
} from '@/api/trends'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import Badge from '@/components/ui/badge/Badge.vue'
import { toast } from '@/components/ui/toast'

const config = ref<TrendDailyReportConfig | null>(null)
const latestReport = ref<TrendDailyReport | null>(null)
const trendKeywords = ref<TrendKeyword[]>([])
const keywordInput = ref('')
const categoryInput = ref('AI')
const notesInput = ref('')
const candidateLimit = ref(10)
const shouldPush = ref(true)
const isLoading = ref(false)
const isRunning = ref(false)
const isTesting = ref(false)
const isRefreshingSnapshots = ref(false)
const isSyncingTasks = ref(false)
const isCreatingKeyword = ref(false)
const deletingKeywordId = ref<number | null>(null)
const error = ref<string | null>(null)

const reportItems = computed<TrendDailyReportItem[]>(() => {
  const items = latestReport.value?.ai_review?.items
  return Array.isArray(items) ? items : []
})

const scheduleLabel = computed(() => {
  const cron = config.value?.cron || '0 9 * * *'
  if (cron === '0 9 * * *') return '每天 09:00'
  return cron
})

const statusCards = computed(() => [
  {
    label: '定时任务',
    value: config.value?.enabled ? '已启用' : '已停用',
    detail: scheduleLabel.value,
    icon: CalendarClock,
    tone: config.value?.enabled ? 'text-emerald-600 bg-emerald-50' : 'text-slate-500 bg-slate-100',
  },
  {
    label: 'AI 审核',
    value: config.value?.ai_configured ? '已配置' : '未配置',
    detail: config.value?.ai_configured ? '可生成运营判断' : '将回退到规则评分',
    icon: Sparkles,
    tone: config.value?.ai_configured ? 'text-blue-600 bg-blue-50' : 'text-amber-600 bg-amber-50',
  },
  {
    label: 'Bark 推送',
    value: config.value?.bark_configured ? '已配置' : '未配置',
    detail: latestReport.value?.push_status ? `最近：${latestReport.value.push_status}` : '等待测试',
    icon: Bell,
    tone: config.value?.bark_configured ? 'text-purple-600 bg-purple-50' : 'text-amber-600 bg-amber-50',
  },
])

function formatDateTime(value?: string | null) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function badgeClass(rank?: string) {
  if (rank === 'A') return 'bg-emerald-100 text-emerald-700'
  if (rank === 'B') return 'bg-blue-100 text-blue-700'
  if (rank === 'C') return 'bg-amber-100 text-amber-700'
  return 'bg-slate-100 text-slate-600'
}

async function loadPage() {
  isLoading.value = true
  error.value = null
  try {
    const [configPayload, reportPayload, keywordsPayload] = await Promise.all([
      getDailyReportConfig(),
      getLatestDailyReport(),
      getTrendKeywords({ include_disabled: true }),
    ])
    config.value = configPayload
    latestReport.value = reportPayload
    trendKeywords.value = keywordsPayload
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    isLoading.value = false
  }
}

async function handleCreateKeyword() {
  const keyword = keywordInput.value.trim()
  if (!keyword) {
    toast({ title: '关键词不能为空', variant: 'destructive' })
    return
  }
  isCreatingKeyword.value = true
  error.value = null
  try {
    await createTrendKeyword({
      keyword,
      category: categoryInput.value.trim(),
      notes: notesInput.value.trim(),
      enabled: true,
    })
    keywordInput.value = ''
    notesInput.value = ''
    toast({ title: '关键词已加入观察池', description: keyword })
    await loadPage()
  } catch (e) {
    error.value = (e as Error).message
    toast({ title: '添加失败', description: error.value, variant: 'destructive' })
  } finally {
    isCreatingKeyword.value = false
  }
}

async function handleDeleteKeyword(item: TrendKeyword) {
  deletingKeywordId.value = item.id
  error.value = null
  try {
    await deleteTrendKeyword(item.id)
    trendKeywords.value = trendKeywords.value.filter((keyword) => keyword.id !== item.id)
    toast({ title: '关键词已删除', description: item.keyword })
  } catch (e) {
    error.value = (e as Error).message
    toast({ title: '删除失败', description: error.value, variant: 'destructive' })
  } finally {
    deletingKeywordId.value = null
  }
}

async function handleRunReport() {
  isRunning.value = true
  error.value = null
  try {
    latestReport.value = await runDailyReport({
      candidate_limit: candidateLimit.value,
      push: shouldPush.value,
      refresh_snapshots: true,
    })
    toast({ title: '日报已生成', description: shouldPush.value ? '已尝试发送 Bark 推送。' : '本次未发送推送。' })
    await loadPage()
  } catch (e) {
    error.value = (e as Error).message
    toast({ title: '生成失败', description: error.value, variant: 'destructive' })
  } finally {
    isRunning.value = false
  }
}

async function handleRefreshSnapshots() {
  isRefreshingSnapshots.value = true
  error.value = null
  try {
    const result = await refreshTrendSnapshots({ limit_per_keyword: 40 })
    toast({
      title: '趋势快照已刷新',
      description: `创建 ${result.created_count} 条，跳过 ${result.skipped_count} 个关键词。`,
    })
    await loadPage()
  } catch (e) {
    error.value = (e as Error).message
    toast({ title: '刷新失败', description: error.value, variant: 'destructive' })
  } finally {
    isRefreshingSnapshots.value = false
  }
}

async function handleSyncMonitorTasks() {
  isSyncingTasks.value = true
  error.value = null
  try {
    const result = await syncTrendMonitorTasks({
      cron: '0 */6 * * *',
      max_pages: 2,
      personal_only: true,
      free_shipping: false,
      new_publish_option: '3天内',
      update_existing: true,
    })
    toast({
      title: '监控任务已同步',
      description: `新建 ${result.created_count} 个，更新 ${result.updated_count} 个，已有 ${result.existing_count} 个。`,
    })
    await loadPage()
  } catch (e) {
    error.value = (e as Error).message
    toast({ title: '同步失败', description: error.value, variant: 'destructive' })
  } finally {
    isSyncingTasks.value = false
  }
}

async function handleTestBark() {
  isTesting.value = true
  error.value = null
  try {
    const result = await sendDailyReportTest({
      title: '闲鱼 AI 机会日报测试',
      body: '这是一条来自 Mac 控制台的 Bark 测试通知。',
    })
    if (result.success) {
      toast({ title: '测试已发送', description: result.message })
    } else {
      toast({ title: '测试失败', description: result.message, variant: 'destructive' })
    }
  } catch (e) {
    error.value = (e as Error).message
    toast({ title: '测试失败', description: error.value, variant: 'destructive' })
  } finally {
    isTesting.value = false
  }
}

onMounted(loadPage)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 class="flex items-center gap-3 text-3xl font-black tracking-tight text-slate-800">
          <Sparkles class="h-8 w-8 text-primary" />
          卖家雷达
        </h1>
        <p class="mt-1 text-sm font-medium text-slate-500">
          每日 AI 机会日报
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button variant="outline" :disabled="isLoading" @click="loadPage">
          <RefreshCw class="mr-2 h-4 w-4" />
          刷新
        </Button>
        <Button variant="outline" :disabled="isTesting" @click="handleTestBark">
          <Send class="mr-2 h-4 w-4" />
          测试 Bark
        </Button>
        <Button variant="outline" :disabled="isRefreshingSnapshots" @click="handleRefreshSnapshots">
          <RefreshCw class="mr-2 h-4 w-4" />
          刷新趋势快照
        </Button>
        <Button variant="outline" :disabled="isSyncingTasks || trendKeywords.length === 0" @click="handleSyncMonitorTasks">
          <WandSparkles class="mr-2 h-4 w-4" />
          同步监控任务
        </Button>
      </div>
    </div>

    <div v-if="error" class="app-alert-error" role="alert">
      {{ error }}
    </div>

    <div class="grid gap-4 md:grid-cols-3">
      <Card v-for="item in statusCards" :key="item.label" class="app-surface border-none">
        <CardContent class="p-5">
          <div class="flex items-center justify-between gap-4">
            <div>
              <p class="text-xs font-bold uppercase tracking-wider text-slate-400">{{ item.label }}</p>
              <p class="mt-2 text-xl font-black text-slate-800">{{ item.value }}</p>
              <p class="mt-1 text-xs font-medium text-slate-500">{{ item.detail }}</p>
            </div>
            <div :class="['rounded-xl p-3', item.tone]">
              <component :is="item.icon" class="h-5 w-5" />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <div class="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
      <div class="space-y-6">
        <Card class="app-surface border-none">
          <CardHeader>
            <CardTitle class="text-lg text-slate-800">观察关键词</CardTitle>
          </CardHeader>
          <CardContent class="space-y-5">
            <div class="grid gap-2">
              <Label for="trend-keyword">关键词</Label>
              <Input
                id="trend-keyword"
                v-model="keywordInput"
                placeholder="例如：AI商品图、ComfyUI工作流"
                @keydown.enter.prevent="handleCreateKeyword"
              />
            </div>
            <div class="grid gap-2">
              <Label for="trend-category">分类</Label>
              <Input id="trend-category" v-model="categoryInput" placeholder="AI / 资料 / 软件" />
            </div>
            <div class="grid gap-2">
              <Label for="trend-notes">备注</Label>
              <Textarea
                id="trend-notes"
                v-model="notesInput"
                class="min-h-20"
                placeholder="记录为什么要观察，例如：短视频平台开始出现教程需求"
              />
            </div>
            <Button class="w-full" :disabled="isCreatingKeyword" @click="handleCreateKeyword">
              <Plus class="mr-2 h-4 w-4" />
              {{ isCreatingKeyword ? '添加中...' : '加入观察池' }}
            </Button>
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <p class="text-xs font-bold uppercase tracking-wider text-slate-400">当前关键词</p>
                <Badge variant="secondary" class="bg-slate-100 text-slate-600">{{ trendKeywords.length }}</Badge>
              </div>
              <div v-if="trendKeywords.length === 0" class="rounded-xl border border-dashed border-slate-200 py-6 text-center text-sm text-slate-500">
                暂无关键词
              </div>
              <div v-else class="max-h-72 space-y-2 overflow-auto pr-1">
                <div
                  v-for="item in trendKeywords"
                  :key="item.id"
                  class="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white/80 p-3"
                >
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-2">
                      <p class="truncate text-sm font-bold text-slate-900">{{ item.keyword }}</p>
                      <Badge variant="secondary" class="bg-blue-50 text-blue-700">{{ item.category || '未分类' }}</Badge>
                    </div>
                    <p v-if="item.notes" class="mt-1 line-clamp-2 text-xs text-slate-500">{{ item.notes }}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-8 w-8 shrink-0 text-slate-400 hover:text-red-600"
                    :disabled="deletingKeywordId === item.id"
                    @click="handleDeleteKeyword(item)"
                  >
                    <Trash2 class="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
            <Button variant="outline" class="w-full" :disabled="isSyncingTasks || trendKeywords.length === 0" @click="handleSyncMonitorTasks">
              <WandSparkles class="mr-2 h-4 w-4" />
              {{ isSyncingTasks ? '同步中...' : '同步为监控任务' }}
            </Button>
          </CardContent>
        </Card>

        <Card class="app-surface border-none">
          <CardHeader>
            <CardTitle class="text-lg text-slate-800">手动生成</CardTitle>
          </CardHeader>
          <CardContent class="space-y-5">
            <div class="grid gap-2">
              <Label for="candidate-limit">AI 审核候选数</Label>
              <Input
                id="candidate-limit"
                v-model.number="candidateLimit"
                type="number"
                min="1"
                max="20"
              />
            </div>
            <div class="flex items-center justify-between rounded-xl border border-slate-200 bg-white/70 px-4 py-3">
              <div>
                <p class="text-sm font-semibold text-slate-800">发送 Bark</p>
                <p class="text-xs text-slate-500">{{ shouldPush ? '生成后推送到手机' : '只保存日报' }}</p>
              </div>
              <Switch v-model:checked="shouldPush" />
            </div>
            <Button class="w-full" :disabled="isRunning" @click="handleRunReport">
              <Sparkles class="mr-2 h-4 w-4" />
              {{ isRunning ? '生成中...' : '立即生成日报' }}
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card class="app-surface border-none">
        <CardHeader class="flex flex-col gap-3 border-b border-slate-100 pb-5 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle class="text-lg text-slate-800">最近日报</CardTitle>
            <p class="mt-1 text-sm text-slate-500">
              {{ latestReport ? `${latestReport.report_date} · ${formatDateTime(latestReport.created_at)}` : '暂无日报' }}
            </p>
          </div>
          <Badge
            v-if="latestReport"
            variant="secondary"
            :class="latestReport.push_status === 'sent' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'"
          >
            {{ latestReport.push_status }}
          </Badge>
        </CardHeader>
        <CardContent class="space-y-5 p-6">
          <div v-if="isLoading" class="rounded-xl border border-dashed border-slate-200 py-10 text-center text-sm text-slate-500">
            加载中...
          </div>
          <div v-else-if="!latestReport" class="rounded-xl border border-dashed border-slate-200 py-10 text-center text-sm text-slate-500">
            暂无日报
          </div>
          <template v-else>
            <div class="rounded-xl bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700">
              {{ latestReport.ai_review.daily_summary || '暂无总结' }}
            </div>

            <div v-if="reportItems.length" class="space-y-3">
              <article
                v-for="item in reportItems"
                :key="`${item.snapshot_id}-${item.keyword}`"
                class="rounded-xl border border-slate-200 bg-white/80 p-4"
              >
                <div class="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h2 class="text-base font-bold text-slate-900">{{ item.keyword }}</h2>
                    <p class="mt-1 text-sm text-slate-600">{{ item.why }}</p>
                  </div>
                  <Badge variant="secondary" :class="badgeClass(item.rank)">
                    {{ item.rank || 'D' }}
                  </Badge>
                </div>
                <div class="mt-4 grid gap-3 md:grid-cols-3">
                  <div class="rounded-lg bg-slate-50 p-3">
                    <p class="text-xs font-bold text-slate-400">卖法</p>
                    <p class="mt-1 text-sm text-slate-700">{{ item.sell_angle || '待判断' }}</p>
                  </div>
                  <div class="rounded-lg bg-emerald-50 p-3">
                    <p class="flex items-center gap-1 text-xs font-bold text-emerald-700">
                      <CheckCircle2 class="h-3.5 w-3.5" />
                      优势
                    </p>
                    <p class="mt-1 text-sm text-emerald-800">{{ item.advantages?.slice(0, 2).join('；') || '暂无' }}</p>
                  </div>
                  <div class="rounded-lg bg-amber-50 p-3">
                    <p class="flex items-center gap-1 text-xs font-bold text-amber-700">
                      <TriangleAlert class="h-3.5 w-3.5" />
                      风险
                    </p>
                    <p class="mt-1 text-sm text-amber-800">{{ item.risks?.slice(0, 2).join('；') || '暂无' }}</p>
                  </div>
                </div>
                <p class="mt-3 text-sm font-semibold text-slate-700">
                  {{ item.next_action || '人工查看' }}
                </p>
              </article>
            </div>
            <div v-else class="rounded-xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-500">
              今日暂无明显机会
            </div>

            <pre class="max-h-56 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-5 text-slate-100">{{ latestReport.push_body }}</pre>
          </template>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
