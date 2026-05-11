import { api } from './client'

export type NarrativeStateEntityType =
  | 'character'
  | 'region'
  | 'hook'
  | 'relationship'
  | 'world'
  | 'plot'
  | 'custom'

export type NarrativeStateChangeType =
  | 'status_change'
  | 'death'
  | 'resurrection'
  | 'location_change'
  | 'hook_triggered'
  | 'hook_resolved'
  | 'hook_dropped'
  | 'region_state_change'
  | 'region_destroyed'
  | 'relationship_change'
  | 'world_state_change'
  | 'custom'

export type NarrativeStateChangeStatus = 'proposed' | 'confirmed' | 'applied' | 'rejected'

export interface NarrativeStateChange {
  id: string
  project_id: string
  world_id?: string | null
  scope_type?: string | null
  entity_type: NarrativeStateEntityType | string
  entity_id?: string | null
  entity_name?: string | null
  change_type: NarrativeStateChangeType | string
  status: NarrativeStateChangeStatus
  confirmation_required: boolean
  title: string
  summary: string
  reason: string
  before_state: Record<string, any>
  after_state: Record<string, any>
  diff: Record<string, any>
  metadata: Record<string, any>
  workflow_execution_id?: string | null
  workflow_id?: string | null
  node_id?: string | null
  agent_type?: string | null
  chapter_id?: string | null
  discussion_id?: string | null
  source_text?: string | null
  fingerprint?: string | null
  created_at?: string | null
  confirmed_at?: string | null
  applied_at?: string | null
  rejected_at?: string | null
}

export interface StateChangeQueryParams {
  project_id: string
  entity_type?: NarrativeStateEntityType | string
  entity_id?: string
  status?: NarrativeStateChangeStatus
  change_type?: NarrativeStateChangeType | string
  chapter_id?: string
  world_id?: string
  workflow_execution_id?: string
  limit?: number
}

export interface CreateStateChangeRequest {
  project_id: string
  entity_type?: NarrativeStateEntityType | string
  entity_id?: string | null
  entity_name?: string | null
  change_type?: NarrativeStateChangeType | string
  status?: NarrativeStateChangeStatus
  confirmation_required?: boolean
  title?: string
  summary?: string
  reason?: string
  before_state?: Record<string, any>
  after_state?: Record<string, any>
  diff?: Record<string, any>
  metadata?: Record<string, any>
  workflow_execution_id?: string | null
  workflow_id?: string | null
  node_id?: string | null
  agent_type?: string | null
  chapter_id?: string | null
  discussion_id?: string | null
  source_text?: string | null
  fingerprint?: string | null
}

export interface ApplyStateChangeResult {
  success: boolean
  applied?: boolean
  change?: NarrativeStateChange
  projection?: Record<string, any>
  message?: string
}

function unwrap<T>(response: T | { data: T }): T {
  if (response && typeof response === 'object' && 'data' in response) {
    return (response as { data: T }).data
  }
  return response as T
}

export async function getStateChanges(params: StateChangeQueryParams): Promise<NarrativeStateChange[]> {
  const searchParams = new URLSearchParams({ project_id: params.project_id })
  if (params.entity_type) searchParams.append('entity_type', params.entity_type)
  if (params.entity_id) searchParams.append('entity_id', params.entity_id)
  if (params.status) searchParams.append('status', params.status)
  if (params.change_type) searchParams.append('change_type', params.change_type)
  if (params.chapter_id) searchParams.append('chapter_id', params.chapter_id)
  if (params.world_id) searchParams.append('world_id', params.world_id)
  if (params.workflow_execution_id) searchParams.append('workflow_execution_id', params.workflow_execution_id)
  if (params.limit !== undefined) searchParams.append('limit', String(params.limit))

  const response = await api.get<NarrativeStateChange[]>(`/state-changes?${searchParams.toString()}`)
  return unwrap(response)
}

export async function getStateChange(changeId: string): Promise<NarrativeStateChange> {
  const response = await api.get<NarrativeStateChange>(`/state-changes/${changeId}`)
  return unwrap(response)
}

export async function createStateChange(data: CreateStateChangeRequest): Promise<NarrativeStateChange> {
  const response = await api.post<NarrativeStateChange>('/state-changes', data)
  return unwrap(response)
}

export async function confirmStateChange(changeId: string): Promise<NarrativeStateChange> {
  const response = await api.post<NarrativeStateChange>(`/state-changes/${changeId}/confirm`)
  return unwrap(response)
}

export async function applyStateChange(changeId: string): Promise<ApplyStateChangeResult> {
  const response = await api.post<ApplyStateChangeResult>(`/state-changes/${changeId}/apply`)
  return unwrap(response)
}

export async function rejectStateChange(changeId: string): Promise<NarrativeStateChange> {
  const response = await api.post<NarrativeStateChange>(`/state-changes/${changeId}/reject`)
  return unwrap(response)
}
