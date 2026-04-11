import { api } from './client'

// ==================== Legacy Types (保留旧接口) ====================

export interface Intervention {
  id?: string
  snapshot_id?: string
  intervention_type: 'character_edit' | 'plot_change' | 'hook_modification' | 'relationship_change' | 'world_edit'
  description: string
  details?: Record<string, any>
  affected_hooks?: string[]
  affected_relationships?: string[]
  affected_characters?: string[]
  outcome_rating?: number
  outcome_notes?: string
  created_at?: string
}

export interface SnapshotOption {
  id: string
  name: string
  description?: string
  world_id?: string
  chapter_id?: string
  created_at?: string
}

// ==================== v8 Types ====================

// 干预类型 - 与后端 InterventionType 枚举一致
export type V8InterventionType = 'guidance' | 'correction' | 'direction' | 'override'
export type ExportFormat = 'json' | 'csv' | 'markdown'

// 干预类型中文映射
export const INTERVENTION_TYPE_LABELS: Record<V8InterventionType, string> = {
  guidance: '指导性',
  correction: '纠正性',
  direction: '方向性',
  override: '覆盖性',
}

// 干预类型颜色映射
export const INTERVENTION_TYPE_COLORS: Record<V8InterventionType, string> = {
  guidance: 'text-blue-500',
  correction: 'text-orange-500',
  direction: 'text-purple-500',
  override: 'text-red-500',
}

export interface V8InterventionLog {
  id: string
  project_id: string
  workflow_execution_id: string
  node_id?: string
  agent_type: string
  agent_name: string
  intervention_type: V8InterventionType
  user_message: string
  agent_response?: string
  context_snapshot: Record<string, any>
  response_time_ms?: number
  timestamp?: string  // API 返回的字段名
  created_at?: string  // 兼容字段名
}

export interface V8InterventionCreate {
  project_id: string
  workflow_execution_id: string
  node_id?: string
  agent_type: string
  message: string
}

export interface V8InterventionQuery {
  project_id?: string
  workflow_execution_id?: string
  agent_type?: string
  intervention_type?: V8InterventionType
  keyword?: string
  limit?: number
  offset?: number
}

export interface V8InterventionSummary {
  total_count: number
  by_agent_type: Record<string, number>
  by_intervention_type: Record<string, number>
  avg_response_time_ms?: number
  recent_interventions: V8InterventionLog[]
}

// ==================== Legacy API Functions ====================

export async function getInterventions() {
  return await api.get<Intervention[]>('/plots/interventions')
}

export async function createIntervention(data: Intervention) {
  return await api.post<{ success: boolean; id: string; message: string }>('/plots/interventions', data)
}

export async function updateInterventionEvaluation(
  interventionId: string,
  data: { outcome_rating?: number; outcome_notes?: string }
) {
  return await api.put<{ success: boolean; data: Intervention }>(
    `/plots/interventions/${interventionId}/evaluation`,
    data,
  )
}

export async function getSnapshots(worldId?: string) {
  return await api.get<SnapshotOption[]>('/plots/snapshots', {
    params: worldId ? { world_id: worldId } : {},
  })
}

/**
 * 删除干预记录 (Legacy)
 */
export async function deleteIntervention(
  interventionId: string,
): Promise<{ success: boolean; message: string }> {
  return await api.delete(`/plots/interventions/${interventionId}`)
}

// ==================== v8 API Functions ====================

/**
 * 获取干预日志列表 (v8)
 */
export async function getV8Interventions(
  query: V8InterventionQuery,
): Promise<V8InterventionLog[]> {
  return await api.get<V8InterventionLog[]>('/interventions', { params: query })
}

/**
 * 发送干预消息 (v8)
 */
export async function sendV8Intervention(
  data: V8InterventionCreate,
): Promise<{
  success: boolean
  message: string
  agent_response?: string
  agent_name?: string
  response_time_ms?: number
  intervention_id?: string
  intervention_type?: V8InterventionType
}> {
  return await api.post('/interventions', data)
}

/**
 * 获取干预详情 (v8)
 */
export async function getV8Intervention(interventionId: string): Promise<V8InterventionLog> {
  return await api.get<V8InterventionLog>(`/interventions/${interventionId}`)
}

/**
 * 获取干预摘要 (v8)
 */
export async function getV8InterventionSummary(
  projectId: string,
  executionId?: string,
): Promise<{
  success: boolean
  summary: V8InterventionSummary
}> {
  return await api.get(`/interventions/summary/${projectId}`, {
    params: { execution_id: executionId },
  })
}

/**
 * 导出干预日志 (v8)
 */
export async function exportV8Interventions(
  projectId: string,
  workflowExecutionId?: string,
  format: ExportFormat = 'json',
  includeContext: boolean = false,
): Promise<{
  success: boolean
  format: string
  content: string
  filename: string
}> {
  return await api.get('/interventions/export', {
    params: {
      project_id: projectId,
      workflow_execution_id: workflowExecutionId,
      format,
      include_context: includeContext,
    },
  })
}

/**
 * 获取消息历史 (v8)
 */
export async function getMessageHistory(
  executionId: string,
  agentType?: string,
): Promise<Array<{
  id: string
  agent_type: string
  message: string
  response?: string
  timestamp: string
}>> {
  return await api.get(`/interventions/history/${executionId}`, {
    params: { agent_type: agentType },
  })
}

/**
 * 删除单个干预日志 (v8)
 */
export async function deleteV8Intervention(
  interventionId: string,
): Promise<{ success: boolean; message: string; deleted_id: string }> {
  return await api.delete(`/interventions/${interventionId}`)
}

/**
 * 删除某次执行的所有干预日志 (v8)
 */
export async function deleteInterventionsByExecution(
  executionId: string,
): Promise<{ success: boolean; message: string; deleted_count: number }> {
  return await api.delete(`/interventions/execution/${executionId}`)
}
