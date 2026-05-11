import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, DatabaseZap, History, Loader2, RefreshCw, RotateCcw, ShieldCheck } from 'lucide-react'

import {
  forceRereadProject,
  getLatestSnapshot,
  resetAndReread,
  resetAssistantHistory,
  type AssistantContextSummary,
  type AssistantForceRereadResponse,
  type AssistantSnapshotStatusResponse,
  type AssistantSurface,
} from '@/api/assistantContext'
import { formatApiErrorMessage } from '@/api/workflows'
import { Modal } from '@/components/ui/Modal'

interface AssistantContextControlsProps {
  projectId: string
  sessionId?: string | null
  assistantSurface: AssistantSurface
  mode?: string
  scope?: Record<string, any>
  contextPacket?: AssistantContextSummary | null
  compact?: boolean
  className?: string
  onHistoryReset?: (newSessionId: string) => void
  onRereadComplete?: (response: AssistantForceRereadResponse) => void
}

type PendingAction = 'reset' | 'reread' | 'reset-reread' | null

const actionCopy: Record<Exclude<PendingAction, null>, { title: string; body: string; confirm: string }> = {
  reset: {
    title: '清空助手历史记录',
    body: '只清空当前助手会话的聊天历史，并开启一个新的会话窗口。项目设定、角色、伏笔、大纲、地图和工作流记录都不会被删除；待确认草稿默认保留。',
    confirm: '确认清空历史',
  },
  reread: {
    title: '重新全量读取项目',
    body: '后端会从数据库重新构建项目上下文快照。下一轮 LLM 必须使用新快照；如果重建失败，本次强制重读不会静默使用旧上下文。当前聊天历史会保留。',
    confirm: '确认重新读取',
  },
  'reset-reread': {
    title: '清空历史并重新读取项目',
    body: '当前助手聊天历史会被清空，并从数据库重建项目上下文快照。下一轮 LLM 将在没有旧聊天包袱的情况下读取最新项目事实。项目数据不会被删除。',
    confirm: '确认清空并重读',
  },
}

export default function AssistantContextControls({
  projectId,
  sessionId,
  assistantSurface,
  mode = 'default',
  scope = {},
  contextPacket,
  compact = false,
  className = '',
  onHistoryReset,
  onRereadComplete,
}: AssistantContextControlsProps) {
  const [snapshot, setSnapshot] = useState<AssistantSnapshotStatusResponse | null>(null)
  const [pendingAction, setPendingAction] = useState<PendingAction>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    getLatestSnapshot(projectId).then(setSnapshot).catch(() => undefined)
  }, [projectId, contextPacket?.snapshot_version])

  const status = contextPacket?.invalidation_state || snapshot?.status || 'unknown'
  const statusLabel = useMemo(() => {
    if (status === 'fresh' || status === 'ready') return '已同步'
    if (status === 'force_rebuilt') return '已全量重读'
    if (status === 'delta_applied') return '已纳入变更'
    if (status === 'failed') return '重建失败'
    if (status === 'stale') return '需刷新'
    return status
  }, [status])

  const snapshotVersion = contextPacket?.snapshot_version ?? snapshot?.snapshot_version
  const tokenEstimate = contextPacket?.token_estimate ?? snapshot?.token_estimate ?? 0

  const requestId = () => `assistant_context_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

  const runAction = async () => {
    if (!pendingAction) return
    setSubmitting(true)
    setError(null)
    try {
      if (pendingAction === 'reset') {
        if (!sessionId) throw new Error('当前助手会话尚未建立，无法清空历史')
        const result = await resetAssistantHistory(projectId, sessionId, {
          assistant_surface: assistantSurface,
          mode,
          delete_message_records: true,
          clear_pending_items: false,
          reason: 'user_requested',
          request_id: requestId(),
        })
        onHistoryReset?.(result.new_session_id)
      } else if (pendingAction === 'reread') {
        const result = await forceRereadProject(projectId, {
          assistant_surface: assistantSurface,
          session_id: sessionId || undefined,
          mode,
          scope,
          clear_history: false,
          clear_pending_items: false,
          reason: 'user_requested_after_project_update',
          request_id: requestId(),
        })
        setSnapshot({
          project_id: projectId,
          snapshot_id: result.snapshot_id,
          snapshot_version: result.snapshot_version,
          status: 'ready',
          token_estimate: result.packet_metadata.token_estimate,
          stale_delta_count: 0,
          built_at: result.packet_metadata.rebuilt_at || null,
        })
        onRereadComplete?.(result)
      } else if (pendingAction === 'reset-reread') {
        if (!sessionId) throw new Error('当前助手会话尚未建立，无法清空历史')
        const result = await resetAndReread(projectId, sessionId, {
          assistant_surface: assistantSurface,
          mode,
          scope,
          clear_pending_items: false,
          reason: 'user_requested_reset_and_reread',
          request_id: requestId(),
        })
        if (result.session_id) onHistoryReset?.(result.session_id)
        onRereadComplete?.(result)
      }
      setPendingAction(null)
    } catch (err) {
      setError(formatApiErrorMessage(err, '助手上下文操作失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={`rounded-2xl border border-sky-200/70 bg-gradient-to-br from-slate-950 via-slate-900 to-sky-950 px-4 py-3 text-sky-50 shadow-lg ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-sky-300/30 bg-sky-300/10 p-2 text-sky-200">
            <DatabaseZap className="h-4 w-4" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              <span>上下文织网</span>
              <span className="rounded-full border border-emerald-300/30 bg-emerald-300/10 px-2 py-0.5 text-xs text-emerald-100">
                {statusLabel}
              </span>
              {snapshotVersion && <span className="text-xs text-sky-200/80">v{snapshotVersion}</span>}
            </div>
            {!compact && (
              <div className="mt-1 text-xs text-sky-100/70">
                本轮约 {tokenEstimate.toLocaleString()} tokens · 引用 {contextPacket?.selected_sections?.length || 0} 组分段 · 未纳入 {contextPacket?.omitted_sections?.length || 0} 组
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setPendingAction('reset')}
            disabled={!sessionId || submitting}
            className="inline-flex items-center gap-1 rounded-lg border border-sky-200/20 px-3 py-1.5 text-xs font-medium text-sky-50 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <History className="h-3.5 w-3.5" /> 清空历史
          </button>
          <button
            type="button"
            onClick={() => setPendingAction('reread')}
            disabled={submitting}
            className="inline-flex items-center gap-1 rounded-lg border border-cyan-200/30 bg-cyan-200/10 px-3 py-1.5 text-xs font-medium text-cyan-50 hover:bg-cyan-200/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5" /> 重新读取
          </button>
          <button
            type="button"
            onClick={() => setPendingAction('reset-reread')}
            disabled={!sessionId || submitting}
            className="inline-flex items-center gap-1 rounded-lg bg-amber-300 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RotateCcw className="h-3.5 w-3.5" /> 清空并重读
          </button>
        </div>
      </div>
      {snapshot?.error_message && (
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-red-300/30 bg-red-400/10 px-3 py-2 text-xs text-red-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-none" /> {snapshot.error_message}
        </div>
      )}

      <Modal
        isOpen={!!pendingAction}
        onClose={() => !submitting && setPendingAction(null)}
        title={pendingAction ? actionCopy[pendingAction].title : '助手上下文操作'}
        size="md"
      >
        {pendingAction && (
          <div className="space-y-4">
            <div className="flex gap-3 rounded-2xl border border-sky-100 bg-sky-50 p-4 text-sm text-slate-700">
              <ShieldCheck className="mt-0.5 h-5 w-5 flex-none text-sky-700" />
              <p>{actionCopy[pendingAction].body}</p>
            </div>
            {error && <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setPendingAction(null)}
                disabled={submitting}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={runAction}
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                {actionCopy[pendingAction].confirm}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
