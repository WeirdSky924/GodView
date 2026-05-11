import { api } from './client'

export type AssistantSurface =
  | 'setting_agent'
  | 'bootstrap_setting_agent'
  | 'plot_outline_agent'
  | 'workflow_intervention'
  | 'world_map_agent'
  | 'volume_planning'
  | 'outline_generation'

export interface AssistantContextSummary {
  packet_id?: string | null
  snapshot_id?: string | null
  snapshot_version?: number | null
  assistant_surface?: string | null
  invalidation_state: string
  force_reread: boolean
  history_reset_applied: boolean
  token_estimate: number
  selected_sections: Array<Record<string, any>>
  omitted_sections: Array<Record<string, any>>
  delta_count: number
  rebuilt_at?: string | null
}

export interface AssistantSessionResponse {
  session_id: string
  project_id: string
  assistant_surface: AssistantSurface | string
  mode: string
  status: string
  snapshot_id?: string | null
  snapshot_version?: number | null
  history_summary: string
  history_window: Array<Record<string, any>>
  pending_items: Array<Record<string, any>>
  context_cursor: Record<string, any>
  created_at?: string | null
  updated_at?: string | null
}

export interface AssistantMessageResponse {
  id: string
  session_id: string
  role: string
  content: string
  request_id?: string | null
  metadata: Record<string, any>
  packet_id?: string | null
  snapshot_id?: string | null
  created_at?: string | null
}

export interface AssistantHistoryResponse {
  session: AssistantSessionResponse
  messages: AssistantMessageResponse[]
  context_packet?: AssistantContextSummary | null
}

export interface AssistantSnapshotStatusResponse {
  project_id: string
  snapshot_id?: string | null
  snapshot_version?: number | null
  status: string
  source_revision_hash?: string | null
  content_hash?: string | null
  token_estimate: number
  stale_delta_count: number
  build_reason?: string | null
  built_at?: string | null
  error_message?: string | null
}

export interface AssistantHistoryResetResponse {
  success: boolean
  old_session_id: string
  new_session_id: string
  history_reset_at: string
  messages_deleted: number
  messages_archived: number
  pending_items_cleared: boolean
  snapshot_id?: string | null
  snapshot_version?: number | null
}

export interface AssistantForceRereadResponse {
  success: boolean
  project_id: string
  session_id?: string | null
  snapshot_id: string
  snapshot_version: number
  previous_snapshot_id?: string | null
  previous_snapshot_version?: number | null
  history_cleared: boolean
  force_reread: boolean
  packet_metadata: AssistantContextSummary
}

export async function createAssistantSession(
  projectId: string,
  data: {
    assistant_surface: AssistantSurface
    mode?: string
    session_id?: string
    scope?: Record<string, any>
    request_id?: string
  },
): Promise<AssistantSessionResponse> {
  return api.post(`/assistant-context/${projectId}/sessions`, data)
}

export async function getAssistantHistory(
  projectId: string,
  sessionId: string,
  limit = 200,
): Promise<AssistantHistoryResponse> {
  return api.get(`/assistant-context/${projectId}/sessions/${sessionId}/history`, { params: { limit } })
}

export async function resetAssistantHistory(
  projectId: string,
  sessionId: string,
  data: {
    assistant_surface: AssistantSurface
    mode?: string
    clear_pending_items?: boolean
    delete_message_records?: boolean
    reason?: string
    request_id?: string
  },
): Promise<AssistantHistoryResetResponse> {
  return api.post(`/assistant-context/${projectId}/sessions/${sessionId}/reset-history`, data)
}

export async function forceRereadProject(
  projectId: string,
  data: {
    assistant_surface: AssistantSurface
    session_id?: string
    mode?: string
    scope?: Record<string, any>
    clear_history?: boolean
    clear_pending_items?: boolean
    reason?: string
    request_id?: string
  },
): Promise<AssistantForceRereadResponse> {
  return api.post(`/assistant-context/${projectId}/force-reread`, data)
}

export async function resetAndReread(
  projectId: string,
  sessionId: string,
  data: {
    assistant_surface: AssistantSurface
    mode?: string
    scope?: Record<string, any>
    clear_pending_items?: boolean
    reason?: string
    request_id?: string
  },
): Promise<AssistantForceRereadResponse> {
  return api.post(`/assistant-context/${projectId}/sessions/${sessionId}/reset-and-reread`, {
    ...data,
    session_id: sessionId,
    clear_history: true,
  })
}

export async function getLatestSnapshot(projectId: string): Promise<AssistantSnapshotStatusResponse> {
  return api.get(`/assistant-context/${projectId}/snapshots/latest`)
}

export async function getContextPacket(projectId: string, packetId: string): Promise<Record<string, any>> {
  return api.get(`/assistant-context/${projectId}/packets/${packetId}`)
}
