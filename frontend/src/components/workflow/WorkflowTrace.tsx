import { useEffect, useMemo, useState } from 'react'
import { GitBranch, RefreshCw } from 'lucide-react'
import { getExecutionTrace } from '@/api/workflows'
import type { ExecutionTrace, TraceArtifact, TraceEvent, TraceSpan } from '@/api/workflows'

interface WorkflowTraceProps {
  executionId: string | null
}

function StatusBadge({ status }: { status?: string }) {
  const color = status === 'completed'
    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
    : status === 'failed'
      ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
      : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
  return <span className={`px-2 py-0.5 rounded text-xs ${color}`}>{status || 'unknown'}</span>
}

function JsonBlock({ value }: { value: any }) {
  if (value === undefined || value === null) return <span className="text-gray-400">无</span>
  return (
    <pre className="text-xs overflow-auto rounded bg-gray-50 dark:bg-gray-900 p-2 max-h-60">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

export default function WorkflowTrace({ executionId }: WorkflowTraceProps) {
  const [trace, setTrace] = useState<ExecutionTrace | null>(null)
  const [spans, setSpans] = useState<TraceSpan[]>([])
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [artifacts, setArtifacts] = useState<TraceArtifact[]>([])
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTrace = async () => {
    if (!executionId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getExecutionTrace(executionId)
      setTrace(data.trace)
      setSpans(data.spans || [])
      setEvents(data.events || [])
      setArtifacts(data.artifacts || [])
      setSelectedSpanId(data.spans?.[0]?.id || null)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || '加载 trace 失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTrace()
  }, [executionId])

  const selectedSpan = useMemo(
    () => spans.find((span) => span.id === selectedSpanId) || null,
    [spans, selectedSpanId],
  )
  const selectedEvents = useMemo(
    () => events.filter((event) => !selectedSpanId || event.span_id === selectedSpanId),
    [events, selectedSpanId],
  )
  const selectedArtifacts = useMemo(
    () => artifacts.filter((artifact) => !selectedSpanId || artifact.span_id === selectedSpanId),
    [artifacts, selectedSpanId],
  )

  if (!executionId) {
    return <div className="h-full flex items-center justify-center text-gray-500">暂无执行记录</div>
  }

  if (loading) {
    return <div className="h-full flex items-center justify-center text-gray-500">加载 Trace...</div>
  }

  if (error) {
    return <div className="p-4 text-sm text-red-600">{error}</div>
  }

  if (!trace) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 text-gray-500">
        <GitBranch size={36} className="opacity-50" />
        <div>该执行暂无 trace</div>
        <button onClick={loadTrace} className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm">刷新</button>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col text-sm">
      <div className="p-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div>
          <div className="font-medium">{trace.root_name || trace.trace_type}</div>
          <div className="text-xs text-gray-500 font-mono">{trace.id}</div>
        </div>
        <button onClick={loadTrace} className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800" title="刷新 Trace">
          <RefreshCw size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-hidden grid grid-cols-2">
        <div className="border-r border-gray-200 dark:border-gray-700 overflow-auto p-2 space-y-1">
          {spans.map((span) => (
            <button
              key={span.id}
              onClick={() => setSelectedSpanId(span.id)}
              className={`w-full text-left rounded p-2 ${selectedSpanId === span.id ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-800'}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium truncate">{span.name}</span>
                <StatusBadge status={span.status} />
              </div>
              <div className="mt-1 text-xs text-gray-500 flex gap-2">
                <span>{span.kind}</span>
                {span.duration_ms !== undefined && <span>{span.duration_ms}ms</span>}
              </div>
            </button>
          ))}
        </div>

        <div className="overflow-auto p-3 space-y-4">
          <section>
            <h3 className="font-medium mb-2">Span</h3>
            {selectedSpan ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2"><StatusBadge status={selectedSpan.status} /><span>{selectedSpan.kind}</span></div>
                <JsonBlock value={selectedSpan.attributes} />
                {selectedSpan.error && <div className="text-red-600 text-xs">{selectedSpan.error}</div>}
              </div>
            ) : (
              <JsonBlock value={trace.metadata} />
            )}
          </section>

          <section>
            <h3 className="font-medium mb-2">Events</h3>
            <div className="space-y-2">
              {selectedEvents.length === 0 && <div className="text-gray-500 text-xs">无事件</div>}
              {selectedEvents.map((event) => (
                <details key={event.id} className="rounded border border-gray-200 dark:border-gray-700 p-2">
                  <summary className="cursor-pointer text-xs font-medium">{event.sequence}. {event.event_type}</summary>
                  <JsonBlock value={event.payload} />
                </details>
              ))}
            </div>
          </section>

          <section>
            <h3 className="font-medium mb-2">Artifacts</h3>
            <div className="space-y-2">
              {selectedArtifacts.length === 0 && <div className="text-gray-500 text-xs">无产物</div>}
              {selectedArtifacts.map((artifact) => (
                <details key={artifact.id} className="rounded border border-gray-200 dark:border-gray-700 p-2">
                  <summary className="cursor-pointer text-xs font-medium">
                    {artifact.kind} · {artifact.size_bytes || 0} bytes · {artifact.redaction_status}
                  </summary>
                  <JsonBlock value={artifact.content ?? artifact.text_content} />
                </details>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
