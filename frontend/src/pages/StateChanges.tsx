import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  AlertCircle,
  Archive,
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileJson,
  Filter,
  FolderOpen,
  GitBranch,
  Loader2,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import PageLayout from '@/components/PageLayout'
import { Button, Card, Modal } from '@/components/ui'
import { useProject } from '@/contexts/ProjectContext'
import { useTheme } from '@/contexts/ThemeContext'
import {
  applyStateChange,
  confirmStateChange,
  getStateChange,
  getStateChanges,
  rejectStateChange,
  type ApplyStateChangeResult,
  type NarrativeStateChange,
  type NarrativeStateChangeStatus,
} from '@/api/stateChanges'

type StatusFilter = 'all' | NarrativeStateChangeStatus
type OwnerAction = 'confirm' | 'apply' | 'reject'

const STATUS_CONFIG: Record<NarrativeStateChangeStatus, { label: string; className: string; icon: typeof Clock3 }> = {
  proposed: { label: '待确认', className: 'bg-amber-100 text-amber-700 border-amber-200', icon: Clock3 },
  confirmed: { label: '已确认', className: 'bg-blue-100 text-blue-700 border-blue-200', icon: ShieldCheck },
  applied: { label: '已应用', className: 'bg-emerald-100 text-emerald-700 border-emerald-200', icon: CheckCircle2 },
  rejected: { label: '已拒绝', className: 'bg-red-100 text-red-700 border-red-200', icon: XCircle },
}

const STATUS_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'proposed', label: '待确认' },
  { value: 'confirmed', label: '已确认' },
  { value: 'applied', label: '已应用' },
  { value: 'rejected', label: '已拒绝' },
]

const ENTITY_OPTIONS = [
  { value: 'all', label: '全部实体' },
  { value: 'character', label: '角色' },
  { value: 'hook', label: '伏笔' },
  { value: 'region', label: '区域' },
  { value: 'relationship', label: '关系' },
  { value: 'world', label: '世界' },
  { value: 'plot', label: '剧情' },
  { value: 'custom', label: '自定义' },
]

const CHANGE_TYPE_OPTIONS = [
  { value: 'all', label: '全部类型' },
  { value: 'status_change', label: '状态变化' },
  { value: 'death', label: '死亡' },
  { value: 'resurrection', label: '复活' },
  { value: 'location_change', label: '位置变化' },
  { value: 'hook_triggered', label: '伏笔触发' },
  { value: 'hook_resolved', label: '伏笔解决' },
  { value: 'hook_dropped', label: '伏笔放弃' },
  { value: 'region_state_change', label: '区域状态' },
  { value: 'region_destroyed', label: '区域毁灭' },
  { value: 'relationship_change', label: '关系变化' },
  { value: 'world_state_change', label: '世界状态' },
  { value: 'custom', label: '自定义' },
]

const ENTITY_LABELS: Record<string, string> = {
  character: '角色',
  hook: '伏笔',
  region: '区域',
  relationship: '关系',
  world: '世界',
  plot: '剧情',
  custom: '自定义',
}

const CHANGE_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  CHANGE_TYPE_OPTIONS.filter(item => item.value !== 'all').map(item => [item.value, item.label])
)

function truncate(value: string, max = 240) {
  if (!value) return ''
  return value.length > max ? `${value.slice(0, max)}…` : value
}

function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function compactJson(value: unknown, max = 180) {
  if (value === undefined || value === null || value === '') return '—'
  if (typeof value === 'string') return truncate(value, max)
  try {
    return truncate(JSON.stringify(value, null, 2), max)
  } catch {
    return String(value)
  }
}

function stableJson(value: unknown) {
  try {
    return JSON.stringify(value ?? null, Object.keys(value && typeof value === 'object' ? value as Record<string, unknown> : {}).sort())
  } catch {
    return String(value)
  }
}

function asObject(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function deriveDiffRows(change: NarrativeStateChange) {
  const explicitDiff = asObject(change.diff)
  if (Object.keys(explicitDiff).length > 0) {
    return Object.entries(explicitDiff).map(([key, value]) => ({ key, before: '—', after: value, source: 'diff' as const }))
  }
  const before = asObject(change.before_state)
  const after = asObject(change.after_state)
  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort()
  return keys
    .filter(key => stableJson(before[key]) !== stableJson(after[key]))
    .map(key => ({ key, before: before[key], after: after[key], source: 'derived' as const }))
}

function DetailField({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs text-gray-500 dark:text-gray-400">{label}</dt>
      <dd className="mt-1 break-all text-sm text-gray-800 dark:text-gray-100">{value || '—'}</dd>
    </div>
  )
}

function StatusBadge({ status }: { status: NarrativeStateChangeStatus }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.proposed
  const Icon = config.icon
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${config.className}`}>
      <Icon size={13} />
      {config.label}
    </span>
  )
}

export default function StateChanges() {
  const { currentProject } = useProject()
  const { theme } = useTheme()
  const isDark = theme === 'dark'
  const [searchParams, setSearchParams] = useSearchParams()
  const initialStatus = (searchParams.get('status') as StatusFilter) || 'proposed'
  const initialChapterId = searchParams.get('chapter_id') || ''
  const initialChangeId = searchParams.get('change_id') || ''

  const [changes, setChanges] = useState<NarrativeStateChange[]>([])
  const [selectedChangeId, setSelectedChangeId] = useState(initialChangeId)
  const [selectedChange, setSelectedChange] = useState<NarrativeStateChange | null>(null)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(STATUS_OPTIONS.some(item => item.value === initialStatus) ? initialStatus : 'proposed')
  const [entityFilter, setEntityFilter] = useState('all')
  const [changeTypeFilter, setChangeTypeFilter] = useState('all')
  const [chapterFilter, setChapterFilter] = useState(initialChapterId)
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [action, setAction] = useState<OwnerAction | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [lastApplyResult, setLastApplyResult] = useState<ApplyStateChangeResult | null>(null)

  const counts = useMemo(() => changes.reduce(
    (acc, change) => {
      acc[change.status] = (acc[change.status] || 0) + 1
      return acc
    },
    {} as Record<NarrativeStateChangeStatus, number>
  ), [changes])

  const loadChanges = useCallback(async (nextSelectedId?: string) => {
    if (!currentProject?.id) {
      setChanges([])
      setSelectedChange(null)
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await getStateChanges({
        project_id: currentProject.id,
        status: statusFilter === 'all' ? undefined : statusFilter,
        entity_type: entityFilter === 'all' ? undefined : entityFilter,
        change_type: changeTypeFilter === 'all' ? undefined : changeTypeFilter,
        chapter_id: chapterFilter || undefined,
        limit: 250,
      })
      setChanges(data)
      const preferredId = nextSelectedId || selectedChangeId || data[0]?.id || ''
      const preferred = data.find(change => change.id === preferredId) || data[0] || null
      setSelectedChangeId(preferred?.id || '')
      setSelectedChange(preferred)
    } catch (e) {
      console.error('Failed to load state changes:', e)
      setError(e instanceof Error ? e.message : '加载状态变更失败')
    } finally {
      setLoading(false)
    }
  }, [changeTypeFilter, chapterFilter, currentProject?.id, entityFilter, selectedChangeId, statusFilter])

  const loadSelectedChange = useCallback(async (changeId: string) => {
    if (!changeId) return
    setDetailLoading(true)
    setError('')
    try {
      const detail = await getStateChange(changeId)
      setSelectedChange(detail)
      setSelectedChangeId(detail.id)
    } catch (e) {
      console.error('Failed to load state change detail:', e)
      setError(e instanceof Error ? e.message : '加载状态变更详情失败')
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadChanges(initialChangeId || undefined)
  }, [loadChanges, initialChangeId])

  useEffect(() => {
    if (initialChangeId) {
      void loadSelectedChange(initialChangeId)
    }
  }, [initialChangeId, loadSelectedChange])

  const updateQuery = (patch: Record<string, string>) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(patch).forEach(([key, value]) => {
      if (value) next.set(key, value)
      else next.delete(key)
    })
    setSearchParams(next, { replace: true })
  }

  const selectChange = (change: NarrativeStateChange) => {
    setSelectedChangeId(change.id)
    setSelectedChange(change)
    setLastApplyResult(null)
    updateQuery({ change_id: change.id })
  }

  const refreshAfterAction = async (changeId: string, message: string, applyResult?: ApplyStateChangeResult) => {
    setNotice(message)
    setLastApplyResult(applyResult || null)
    await loadSelectedChange(changeId)
    await loadChanges(changeId)
  }

  const runAction = async () => {
    if (!selectedChange || !action) return
    setActionLoading(true)
    setError('')
    try {
      if (action === 'confirm') {
        await confirmStateChange(selectedChange.id)
        await refreshAfterAction(selectedChange.id, '状态变更已确认，可进入后续前文状态交接。')
      } else if (action === 'apply') {
        const result = await applyStateChange(selectedChange.id)
        await refreshAfterAction(selectedChange.id, result.message || '状态变更已应用。', result)
      } else {
        await rejectStateChange(selectedChange.id)
        await refreshAfterAction(selectedChange.id, '状态变更已拒绝，不会进入已确认前文状态。')
      }
      setAction(null)
    } catch (e) {
      console.error('Failed to run state change action:', e)
      setError(e instanceof Error ? e.message : '状态变更操作失败')
    } finally {
      setActionLoading(false)
    }
  }

  const actionCopy = useMemo(() => {
    if (!selectedChange || !action) return null
    if (action === 'confirm') {
      return {
        title: '确认叙事状态',
        body: '确认后，这条变更会被视为作者认可的正史候选，并可进入后续 Writer/Evaluator 的已确认前文状态包。此操作不会直接改写角色、伏笔或区域表。',
        button: '确认状态',
        variant: 'primary' as const,
      }
    }
    if (action === 'apply') {
      const logOnly = !['character', 'hook', 'region'].includes(String(selectedChange.entity_type))
      return {
        title: '应用叙事状态',
        body: logOnly
          ? '该实体类型当前是审计记录 / log-only。应用后会标记为已应用，并进入已确认前文状态，但不会投影到具体实体表。'
          : '应用后会将已确认变更投影到当前角色、伏笔或区域状态表，并影响后续生成上下文。请确认该变化应成为当前正史。',
        button: '应用状态',
        variant: 'primary' as const,
      }
    }
    return {
      title: '拒绝叙事状态',
      body: '拒绝后，这条变更不会作为 confirmed/applied 正史进入后续生成上下文。已拒绝变更不可再确认或应用。',
      button: '拒绝状态',
      variant: 'danger' as const,
    }
  }, [action, selectedChange])

  const diffRows = selectedChange ? deriveDiffRows(selectedChange) : []

  const filters = (
    <div className="flex flex-wrap items-center gap-3">
      <div className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
        <Filter size={16} />
        筛选
      </div>
      <select
        value={statusFilter}
        onChange={(event) => {
          const value = event.target.value as StatusFilter
          setStatusFilter(value)
          updateQuery({ status: value === 'all' ? '' : value, change_id: '' })
        }}
        className={`rounded-lg border px-3 py-2 text-sm ${isDark ? 'border-gray-700 bg-gray-800 text-gray-100' : 'border-gray-200 bg-white text-gray-700'}`}
      >
        {STATUS_OPTIONS.map(option => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      <select
        value={entityFilter}
        onChange={(event) => setEntityFilter(event.target.value)}
        className={`rounded-lg border px-3 py-2 text-sm ${isDark ? 'border-gray-700 bg-gray-800 text-gray-100' : 'border-gray-200 bg-white text-gray-700'}`}
      >
        {ENTITY_OPTIONS.map(option => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      <select
        value={changeTypeFilter}
        onChange={(event) => setChangeTypeFilter(event.target.value)}
        className={`rounded-lg border px-3 py-2 text-sm ${isDark ? 'border-gray-700 bg-gray-800 text-gray-100' : 'border-gray-200 bg-white text-gray-700'}`}
      >
        {CHANGE_TYPE_OPTIONS.map(option => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      {chapterFilter && (
        <button
          type="button"
          onClick={() => {
            setChapterFilter('')
            updateQuery({ chapter_id: '', change_id: '' })
          }}
          className={`rounded-full px-3 py-1 text-xs ${isDark ? 'bg-blue-900/40 text-blue-200' : 'bg-blue-50 text-blue-700'}`}
        >
          章节过滤：{chapterFilter.slice(0, 8)} ×
        </button>
      )}
    </div>
  )

  if (!currentProject) {
    return (
      <PageLayout title="叙事状态确认" description="审核 Agent 提出的角色、地点、伏笔与世界状态变更">
        <div className="flex h-full items-center justify-center">
          <div className="text-center">
            <FolderOpen className="mx-auto mb-4 h-12 w-12 text-gray-400" />
            <p className="text-gray-500 dark:text-gray-400">请先在侧边栏选择一个项目</p>
          </div>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout
      title="叙事状态确认"
      description="审核 Agent 提出的角色、地点、伏笔与世界状态变更，决定哪些进入后续生成正史"
      filters={filters}
      actions={(
        <Button variant="secondary" size="sm" onClick={() => void loadChanges(selectedChangeId)} loading={loading}>
          <RefreshCw size={16} className="mr-2" />
          刷新
        </Button>
      )}
    >
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {(['proposed', 'confirmed', 'applied', 'rejected'] as NarrativeStateChangeStatus[]).map(status => (
          <Card key={status} className="px-4 py-3" noPadding>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">{STATUS_CONFIG[status].label}</span>
              <StatusBadge status={status} />
            </div>
            <div className="mt-2 text-2xl font-bold text-gray-900 dark:text-white">{counts[status] || 0}</div>
          </Card>
        ))}
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
          <AlertCircle size={16} className="mt-0.5" />
          <span>{error}</span>
        </div>
      )}
      {notice && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
          <CheckCircle2 size={16} className="mt-0.5" />
          <span>{notice}</span>
        </div>
      )}

      <div className="grid h-[calc(100vh-18rem)] grid-cols-1 gap-4 xl:grid-cols-[420px_1fr]">
        <Card noPadding className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
            <div>
              <h2 className="font-semibold text-gray-900 dark:text-white">状态队列</h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">{changes.length} 条变更</p>
            </div>
            {loading && <Loader2 className="h-5 w-5 animate-spin text-blue-500" />}
          </div>
          <div className="h-full overflow-y-auto p-3">
            {!loading && changes.length === 0 && (
              <div className="flex h-64 flex-col items-center justify-center text-center text-gray-500 dark:text-gray-400">
                <Archive className="mb-3 h-10 w-10" />
                <p>当前筛选下没有状态变更</p>
              </div>
            )}
            <div className="space-y-2">
              {changes.map(change => {
                const selected = selectedChangeId === change.id
                return (
                  <button
                    type="button"
                    key={change.id}
                    onClick={() => selectChange(change)}
                    className={`w-full rounded-xl border p-3 text-left transition ${
                      selected
                        ? isDark ? 'border-blue-500 bg-blue-950/30' : 'border-blue-400 bg-blue-50'
                        : isDark ? 'border-gray-700 bg-gray-800/40 hover:border-gray-600' : 'border-gray-200 bg-white hover:border-blue-200 hover:bg-blue-50/40'
                    }`}
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold text-gray-900 dark:text-white">
                          {change.title || change.summary || change.id}
                        </h3>
                        <p className="mt-1 line-clamp-2 text-xs text-gray-500 dark:text-gray-400">
                          {change.summary || '无摘要'}
                        </p>
                      </div>
                      <StatusBadge status={change.status} />
                    </div>
                    <div className="flex flex-wrap gap-1.5 text-xs">
                      <span className="rounded bg-gray-100 px-2 py-0.5 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                        {ENTITY_LABELS[String(change.entity_type)] || change.entity_type}
                      </span>
                      <span className="rounded bg-gray-100 px-2 py-0.5 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                        {CHANGE_TYPE_LABELS[String(change.change_type)] || change.change_type}
                      </span>
                      {change.chapter_id && (
                        <span className="rounded bg-blue-100 px-2 py-0.5 text-blue-700 dark:bg-blue-900/40 dark:text-blue-200">
                          章节 {String(change.chapter_id).slice(0, 8)}
                        </span>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        </Card>

        <Card noPadding className="overflow-hidden">
          {!selectedChange ? (
            <div className="flex h-full flex-col items-center justify-center text-gray-500 dark:text-gray-400">
              <GitBranch className="mb-3 h-12 w-12" />
              <p>选择一条状态变更查看详情</p>
            </div>
          ) : (
            <div className="h-full overflow-y-auto">
              <div className="border-b border-gray-200 p-5 dark:border-gray-700">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <StatusBadge status={selectedChange.status} />
                      {selectedChange.confirmation_required && (
                        <span className="rounded-full bg-purple-100 px-2.5 py-1 text-xs font-semibold text-purple-700 dark:bg-purple-900/40 dark:text-purple-200">
                          需要确认
                        </span>
                      )}
                    </div>
                    <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                      {selectedChange.title || selectedChange.summary || selectedChange.id}
                    </h2>
                    <p className="mt-2 max-w-3xl text-sm text-gray-600 dark:text-gray-300">
                      {selectedChange.summary || '无摘要'}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selectedChange.status === 'proposed' && (
                      <>
                        <Button size="sm" onClick={() => setAction('confirm')}>确认</Button>
                        <Button size="sm" variant="danger" onClick={() => setAction('reject')}>拒绝</Button>
                      </>
                    )}
                    {selectedChange.status === 'confirmed' && (
                      <>
                        <Button size="sm" onClick={() => setAction('apply')}>应用</Button>
                        <Button size="sm" variant="danger" onClick={() => setAction('reject')}>拒绝</Button>
                      </>
                    )}
                  </div>
                </div>
                {detailLoading && <p className="mt-3 text-sm text-blue-500">正在刷新详情…</p>}
              </div>

              <div className="grid gap-4 p-5 xl:grid-cols-[1.1fr_0.9fr]">
                <div className="space-y-4">
                  <section>
                    <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">叙事影响</h3>
                    <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
                      <p className="text-sm text-gray-700 dark:text-gray-200">{selectedChange.reason || '未记录触发理由'}</p>
                      <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-3">
                        <DetailField label="实体类型" value={ENTITY_LABELS[String(selectedChange.entity_type)] || String(selectedChange.entity_type)} />
                        <DetailField label="变更类型" value={CHANGE_TYPE_LABELS[String(selectedChange.change_type)] || String(selectedChange.change_type)} />
                        <DetailField label="实体名称" value={selectedChange.entity_name} />
                        <DetailField label="实体 ID" value={selectedChange.entity_id} />
                        <DetailField label="世界 ID" value={selectedChange.world_id} />
                        <DetailField label="作用域" value={selectedChange.scope_type} />
                      </div>
                    </div>
                  </section>

                  <section>
                    <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">状态差异</h3>
                    <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700">
                      {diffRows.length === 0 ? (
                        <div className="p-4 text-sm text-gray-500 dark:text-gray-400">未记录结构化差异</div>
                      ) : (
                        <div className="divide-y divide-gray-200 dark:divide-gray-700">
                          {diffRows.map(row => (
                            <div key={row.key} className="grid gap-3 p-4 md:grid-cols-[160px_1fr_1fr]">
                              <div className="text-sm font-medium text-gray-700 dark:text-gray-200">{row.key}</div>
                              <pre className="whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-xs text-gray-600 dark:bg-gray-900 dark:text-gray-300">{compactJson(row.before)}</pre>
                              <pre className="whitespace-pre-wrap rounded-lg bg-emerald-50 p-3 text-xs text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200">{compactJson(row.after)}</pre>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </section>

                  {lastApplyResult && (
                    <section>
                      <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">最近应用结果</h3>
                      <pre className="max-h-48 overflow-auto rounded-xl border border-gray-200 bg-gray-50 p-4 text-xs text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200">
                        {JSON.stringify(lastApplyResult.projection || lastApplyResult, null, 2)}
                      </pre>
                    </section>
                  )}
                </div>

                <div className="space-y-4">
                  <section>
                    <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">生命周期</h3>
                    <dl className="grid grid-cols-2 gap-3 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
                      <DetailField label="创建" value={formatDate(selectedChange.created_at)} />
                      <DetailField label="确认" value={formatDate(selectedChange.confirmed_at)} />
                      <DetailField label="应用" value={formatDate(selectedChange.applied_at)} />
                      <DetailField label="拒绝" value={formatDate(selectedChange.rejected_at)} />
                    </dl>
                  </section>

                  <section>
                    <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">来源与审计</h3>
                    <dl className="space-y-3 rounded-xl border border-gray-200 p-4 dark:border-gray-700">
                      <DetailField label="章节 ID" value={selectedChange.chapter_id} />
                      <DetailField label="执行 ID" value={selectedChange.workflow_execution_id} />
                      <DetailField label="工作流 ID" value={selectedChange.workflow_id} />
                      <DetailField label="节点 ID" value={selectedChange.node_id} />
                      <DetailField label="Agent" value={selectedChange.agent_type} />
                      <DetailField label="讨论 ID" value={selectedChange.discussion_id} />
                      <DetailField label="指纹" value={selectedChange.fingerprint} />
                    </dl>
                  </section>

                  {selectedChange.source_text && (
                    <section>
                      <h3 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">来源摘录</h3>
                      <div className="rounded-xl border border-gray-200 p-4 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
                        {truncate(selectedChange.source_text, 600)}
                      </div>
                    </section>
                  )}

                  <section>
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                      <FileJson size={16} />
                      原始状态片段
                    </h3>
                    <details className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
                      <summary className="cursor-pointer text-sm font-medium text-gray-700 dark:text-gray-200">展开 JSON</summary>
                      <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap text-xs text-gray-600 dark:text-gray-300">
                        {JSON.stringify({ before_state: selectedChange.before_state, after_state: selectedChange.after_state, diff: selectedChange.diff, metadata: selectedChange.metadata }, null, 2)}
                      </pre>
                    </details>
                  </section>

                  {selectedChange.chapter_id && (
                    <a
                      href={`/novel?chapter_id=${encodeURIComponent(selectedChange.chapter_id)}`}
                      className="inline-flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-300"
                    >
                      查看关联正文
                      <ExternalLink size={14} />
                    </a>
                  )}
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>

      {actionCopy && selectedChange && (
        <Modal isOpen={!!action} onClose={() => setAction(null)} title={actionCopy.title} size="lg">
          <div className="space-y-4">
            <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-700">
              <StatusBadge status={selectedChange.status} />
              <h3 className="mt-3 font-semibold text-gray-900 dark:text-white">{selectedChange.title || selectedChange.summary || selectedChange.id}</h3>
              <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{selectedChange.summary || '无摘要'}</p>
            </div>
            <p className="text-sm leading-6 text-gray-700 dark:text-gray-200">{actionCopy.body}</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setAction(null)} disabled={actionLoading}>取消</Button>
              <Button variant={actionCopy.variant} onClick={() => void runAction()} loading={actionLoading}>{actionCopy.button}</Button>
            </div>
          </div>
        </Modal>
      )}
    </PageLayout>
  )
}
