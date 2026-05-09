/**
 * 工作流 API 客户端
 * v8 Agent协作可视化工作台
 */

import axios from 'axios'

const API_BASE = '/api'

// ==================== 类型定义 ====================

export type NodeType = 'agent' | 'condition' | 'group_discussion' | 'scene_performance' | 'parallel' | 'start' | 'end' | 'input'
export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
export type WorkflowStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
export type OutputContractMode = 'text' | 'hybrid' | 'strict'

// 数据输入来源
export type DataInputSource = 'database' | 'context' | 'upstream' | 'variable' | 'user_input'

// 数据输出目标
export type DataOutputTarget = 'context' | 'downstream' | 'database'

// 章节资源 readiness gate 阻断详情
export interface ChapterReadinessGateDetail {
  readiness_status?: string
  block_reason?: string
  message?: string
  chapter_num?: number | string | null
  chapter_outline_id?: string | null
  outline_status?: string | null
  readiness?: Record<string, any> | null
  blocking_requirements?: Array<Record<string, any>>
  advisory_requirements?: Array<Record<string, any>>
  [key: string]: any
}

// 节点输入配置
export interface NodeInputConfig {
  name: string
  source: DataInputSource
  data_type?: string
  key?: string
  upstream_node?: string
  upstream_field?: string
  required: boolean
  default?: any
}

// 节点输出配置
export interface NodeOutputConfig {
  name: string
  target: DataOutputTarget
  key?: string
  contract_id?: string
  save_to_db: boolean
  db_table?: string
}

export interface WorkflowNode {
  id: string
  node_type: NodeType
  agent_type?: string
  label: string
  description?: string
  config: Record<string, any>
  // 数据传递配置
  inputs?: NodeInputConfig[]
  outputs?: NodeOutputConfig[]
  position: { x: number; y: number }
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  label?: string
  condition?: Record<string, any>
}

export interface WorkflowDefinition {
  id: string
  project_id: string | null
  name: string
  description?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  variables: Record<string, any>
  is_template: boolean
  created_at: string
  updated_at: string
}

export interface WorkflowDefinitionCreate {
  project_id: string
  name: string
  description?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  variables?: Record<string, any>
  is_template?: boolean
}

export interface WorkflowDefinitionUpdate {
  name?: string
  description?: string
  nodes?: WorkflowNode[]
  edges?: WorkflowEdge[]
  variables?: Record<string, any>
  is_template?: boolean
}

export interface NodeExecutionState {
  node_id: string
  status: NodeStatus
  started_at?: string
  completed_at?: string
  input_data: Record<string, any>
  output_data: Record<string, any>
  output_contract_id?: string
  output_mode?: OutputContractMode
  output_schema_name?: string
  output_schema_version?: string
  error?: string
  retry_count?: number
  duration_ms?: number
}

export interface WorkflowOperationCapability {
  allowed: boolean
  label: string
  reason?: string | null
  severity?: 'info' | 'warning' | 'blocking' | string
  next_status?: WorkflowStatus | string | null
}

export interface WorkflowOperationEvent {
  sequence_no?: number | null
  event_type: string
  created_at?: string | null
  summary: string
  node_id?: string | null
  status?: string | null
  severity: 'info' | 'warning' | 'error' | string
  data: Record<string, any>
}

export interface WorkflowOperationSummary {
  execution_id: string
  workflow_id: string
  project_id: string
  status: WorkflowStatus
  current_node?: string | null
  active_task: boolean
  terminal: boolean
  capabilities: Record<'pause' | 'resume' | 'cancel' | 'recover' | 'remediate', WorkflowOperationCapability>
  node_summary: {
    total: number
    counts: Record<string, number>
    failed_node_id?: string | null
    failed_node_error?: string | null
    failed_nodes?: Array<Record<string, any>>
  }
  lease: {
    lease_expires_at?: string | null
    last_heartbeat_at?: string | null
    expired: boolean
    seconds_remaining?: number | null
    cancel_requested?: boolean | null
  }
  recovery: {
    count: number
    latest?: WorkflowRecoveryHistoryEntry | null
    resume_cursor?: Record<string, any> | null
  }
  remediation: {
    count: number
    latest?: Record<string, any> | null
  }
  stale: {
    count: number
    latest?: Record<string, any> | null
  }
  attention: Array<{ type: string; severity: string; message: string }>
}

export interface WorkflowExecution {
  id: string
  workflow_id: string
  project_id: string
  status: WorkflowStatus
  current_node?: string
  node_states: Record<string, NodeExecutionState>
  context: Record<string, any>
  intervention_ids: string[]
  started_at: string
  completed_at?: string
  total_duration_ms?: number
  error?: string
  trace_id?: string
  request_id?: string
  request_hash?: string
  director_session_id?: string
  operation_id?: string
  lease_token?: string
  lease_expires_at?: string
  last_heartbeat_at?: string
  resume_cursor?: Record<string, any>
  cancel_requested?: boolean
  operation_summary?: WorkflowOperationSummary
}

export interface ExecutionTrace {
  id: string
  project_id?: string
  operation_id?: string
  request_id?: string
  workflow_id?: string
  workflow_execution_id?: string
  trace_type: string
  root_name?: string
  status: string
  root_input_summary?: Record<string, any>
  metadata?: Record<string, any>
  started_at?: string
  ended_at?: string
  duration_ms?: number
  error?: string
}

export interface TraceSpan {
  id: string
  trace_id: string
  parent_span_id?: string | null
  name: string
  kind: string
  status: string
  workflow_id?: string
  workflow_execution_id?: string
  node_id?: string
  agent_type?: string
  attributes?: Record<string, any>
  started_at?: string
  ended_at?: string
  duration_ms?: number
  error?: string
}

export interface TraceEvent {
  id: string
  trace_id: string
  span_id?: string | null
  sequence?: number
  event_type: string
  severity?: string
  payload?: Record<string, any>
  created_at?: string
}

export interface TraceArtifact {
  id: string
  trace_id: string
  span_id?: string | null
  kind: string
  content_type?: string
  content?: any
  text_content?: string
  content_hash?: string
  size_bytes?: number
  redaction_status?: string
  created_at?: string
}

export interface WorkflowValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
  node_count: number
  edge_count: number
  has_cycle?: boolean
  is_connected?: boolean
}

export interface WorkflowEventMessage {
  type: string
  execution_id: string
  data: Record<string, any>
  sequence_no?: number
  replayed?: boolean
}

export type WorkflowSseState = 'connecting' | 'connected' | 'degraded' | 'closed'
export type WorkflowRecoveryMode = 'retry_failed' | 'retry_from_node'

export interface WorkflowRecoveryHistoryEntry {
  attempt?: number
  mode?: WorkflowRecoveryMode | string
  target_node_id?: string
  reset_node_ids?: string[]
  reason?: string
  started_at?: string
  previous_error?: string | null
  previous_completed_at?: string | null
  trace_id?: string | null
  status_at_start?: string
}

export interface WorkflowExecutionHistoryRow {
  id: string
  workflow_id: string
  project_id: string
  status: WorkflowStatus
  current_node?: string | null
  started_at?: string | null
  completed_at?: string | null
  total_duration_ms?: number | null
  trace_id?: string | null
  error?: string | null
  node_count?: number
  completed_node_count?: number
  failed_node_id?: string | null
  recovery_count?: number
  latest_recovery?: WorkflowRecoveryHistoryEntry | null
  resume_cursor?: Record<string, any> | null
}

export interface WorkflowRecoveryRequest {
  mode?: WorkflowRecoveryMode
  node_id?: string
  reason?: string
  context_patch?: Record<string, any>
  reset_downstream?: boolean
}

export interface WorkflowRecoveryResponse {
  success: boolean
  message: string
  execution_id: string
  status: WorkflowStatus
  recovered_node_id?: string
  reset_node_ids?: string[]
  recovery_attempt?: number
  trace_id?: string
  recovery_entry?: WorkflowRecoveryHistoryEntry
}

export interface WorkflowFailureDiagnosis {
  execution_id: string
  workflow_id: string
  failed_node_id: string
  failed_node_label?: string
  category: string
  severity: string
  recoverable: boolean
  retry_without_fix_likely_to_fail: boolean
  remediable: boolean
  summary: string
  evidence: string[]
  current_agent_type?: string | null
  current_scenario?: string | null
  suggested_actions: Array<{ type: string; label: string; fields?: string[] }>
}

export interface WorkflowNodeRemediationPatch {
  agent_type?: string
  scenario?: string
}

export interface WorkflowRemediationRequest {
  node_id?: string
  reason?: string
  patch: WorkflowNodeRemediationPatch
  context_patch?: Record<string, any>
  reset_downstream?: boolean
}

export interface WorkflowRemediationResponse {
  success: boolean
  message: string
  diagnosis: WorkflowFailureDiagnosis
  remediation_entry: Record<string, any>
  recovery: WorkflowRecoveryResponse
}

// ==================== API 函数 ====================

/**
 * 获取工作流列表
 */
export async function getWorkflows(
  projectId: string,
  includeTemplates: boolean = false,
): Promise<WorkflowDefinition[]> {
  const response = await axios.get(`${API_BASE}/workflows`, {
    params: { project_id: projectId, include_templates: includeTemplates },
  })
  return response.data
}

/**
 * 创建工作流
 */
export async function createWorkflow(
  data: WorkflowDefinitionCreate,
): Promise<{ success: boolean; message: string; workflow: WorkflowDefinition }> {
  const response = await axios.post(`${API_BASE}/workflows`, data)
  return response.data
}

/**
 * 获取工作流详情
 */
export async function getWorkflow(workflowId: string): Promise<WorkflowDefinition> {
  const response = await axios.get(`${API_BASE}/workflows/${workflowId}`)
  return response.data
}

/**
 * 更新工作流
 */
export async function updateWorkflow(
  workflowId: string,
  data: WorkflowDefinitionUpdate,
): Promise<{ success: boolean; message: string; workflow: WorkflowDefinition }> {
  const response = await axios.put(`${API_BASE}/workflows/${workflowId}`, data)
  return response.data
}

/**
 * 删除工作流
 */
export async function deleteWorkflow(
  workflowId: string,
): Promise<{ success: boolean; message: string }> {
  const response = await axios.delete(`${API_BASE}/workflows/${workflowId}`)
  return response.data
}

/**
 * 验证工作流
 */
export async function validateWorkflow(
  workflowId: string,
): Promise<WorkflowValidationResult> {
  const response = await axios.post(`${API_BASE}/workflows/${workflowId}/validate`)
  return response.data
}

/**
 * 执行工作流
 */
export async function executeWorkflow(
  workflowId: string,
  projectId: string,
  initialContext?: Record<string, any>,
  options?: { requestId?: string; forceNew?: boolean },
): Promise<{
  success: boolean
  message: string
  execution_id: string
  workflow_id: string
  status?: WorkflowStatus
  trace_id?: string
  world_id?: string
  deduplicated?: boolean
}> {
  const response = await axios.post(
    `${API_BASE}/workflows/${workflowId}/execute`,
    {
      initial_context: initialContext || {},
      request_id: options?.requestId,
      force_new: options?.forceNew || false,
    },
    { params: { project_id: projectId } },
  )
  return response.data
}

export function extractChapterReadinessGateDetail(error: any): ChapterReadinessGateDetail | null {
  const status = error?.response?.status
  const responseDetail = error?.response?.data?.detail
  const directDetail = error?.detail || error?.data
  const detail = responseDetail || directDetail
  if (status !== 409 && error?.code !== 'chapter_resource_readiness_blocked' && detail?.code !== 'chapter_resource_readiness_blocked') {
    const hasReadinessPayload = detail && (
      Array.isArray(detail.blocking_requirements) ||
      detail.readiness_status === 'blocked' ||
      detail.block_reason
    )
    if (!hasReadinessPayload) return null
  }
  if (!detail || typeof detail !== 'object') return null
  if (detail.detail && typeof detail.detail === 'object') return detail.detail as ChapterReadinessGateDetail
  if (detail.data && typeof detail.data === 'object' && (
    detail.data.readiness_status === 'blocked' ||
    Array.isArray(detail.data.blocking_requirements) ||
    detail.data.block_reason
  )) {
    return detail.data as ChapterReadinessGateDetail
  }
  return detail as ChapterReadinessGateDetail
}

export function isChapterReadinessGateError(error: any): boolean {
  return extractChapterReadinessGateDetail(error) !== null
}

export function isReadinessBlockedStatus(status?: string | null): boolean {
  return status === 'blocked'
}

export function isReadinessWarningStatus(status?: string | null): boolean {
  return status === 'ready_with_warnings'
}

export function isReadinessReadyStatus(status?: string | null): boolean {
  return status === 'ready'
}

export function getReadinessStatusLabel(status?: string | null): string {
  if (status === 'ready') return 'Ready'
  if (status === 'ready_with_warnings') return 'Ready with warnings'
  if (status === 'blocked') return 'Blocked'
  if (status === 'stale') return 'Stale'
  if (status === 'not_audited') return 'Not audited'
  return 'Unknown'
}

export function formatChapterReadinessGateMessage(
  detail: ChapterReadinessGateDetail | null,
  formatRequirements?: (requirements: Array<Record<string, any>>) => string,
): string {
  if (!detail) return '章节资源未就绪，不能启动生成工作流。'
  const message = detail.message || detail.block_reason || '章节资源未就绪，不能启动生成工作流。'
  const contextParts = [
    detail.chapter_num !== undefined && detail.chapter_num !== null ? `章节：${detail.chapter_num}` : '',
    detail.chapter_outline_id ? `大纲版本：${detail.chapter_outline_id}` : '',
    detail.outline_status ? `大纲状态：${detail.outline_status}` : '',
    detail.readiness_status ? `readiness：${detail.readiness_status}` : '',
  ].filter(Boolean)
  const blockingRequirements = Array.isArray(detail.blocking_requirements) ? detail.blocking_requirements : []
  const advisoryRequirements = Array.isArray(detail.advisory_requirements) ? detail.advisory_requirements : []
  const requirementParts = [
    blockingRequirements.length
      ? `阻塞资源：${formatRequirements ? formatRequirements(blockingRequirements) : `${blockingRequirements.length} 项`}`
      : '',
    advisoryRequirements.length
      ? `建议资源：${formatRequirements ? formatRequirements(advisoryRequirements) : `${advisoryRequirements.length} 项`}`
      : '',
  ].filter(Boolean)
  return [message, ...contextParts, ...requirementParts].join('；')
}

export function formatApiErrorMessage(error: any, fallback = '操作失败'): string {
  const gateDetail = extractChapterReadinessGateDetail(error)
  if (gateDetail) return formatChapterReadinessGateMessage(gateDetail)
  const detail = error?.response?.data?.detail || error?.detail || error?.data
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail?.results)) {
    const failed = detail.results.filter((item: any) => item?.status === 'failed')
    const failureDetails = failed
      .map((item: any) => `第${item.chapter_number ?? '?'}章：${item.error || item.error_type || '保存失败'}`)
      .join('\n')
    return failureDetails ? `${detail.message || fallback}\n${failureDetails}` : (detail.message || fallback)
  }
  if (detail?.message) return detail.message
  if (detail?.error) return detail.error
  if (error?.message) return error.message
  return fallback
}

/**
 * 获取当前活跃执行
 */
export async function getActiveWorkflowExecution(
  projectId: string,
  workflowId?: string,
  directorSessionId?: string,
): Promise<{ success: boolean; execution: WorkflowExecution | null }> {
  const response = await axios.get(`${API_BASE}/workflows/executions/active`, {
    params: { project_id: projectId, workflow_id: workflowId, director_session_id: directorSessionId },
  })
  return response.data
}

/**
 * 获取执行状态
 */
export async function getExecution(executionId: string): Promise<WorkflowExecution> {
  const response = await axios.get(`${API_BASE}/workflows/executions/${executionId}`)
  return response.data
}

export async function getExecutionOperationSummary(executionId: string): Promise<WorkflowOperationSummary> {
  const response = await axios.get(`${API_BASE}/workflows/executions/${executionId}/operation-summary`)
  return response.data.summary
}

export async function getExecutionOperationEvents(
  executionId: string,
  limit: number = 50,
): Promise<WorkflowOperationEvent[]> {
  const response = await axios.get(`${API_BASE}/workflows/executions/${executionId}/operation-events`, {
    params: { limit },
  })
  return response.data.events || []
}

/**
 * 创建工作流执行 SSE 连接
 */
export function createWorkflowExecutionEventSource(executionId: string): EventSource {
  return new EventSource(`${API_BASE}/workflows/executions/${executionId}/events`)
}

/**
 * 获取执行 Trace
 */
export async function getExecutionTrace(executionId: string): Promise<{
  success: boolean
  trace: ExecutionTrace | null
  spans: TraceSpan[]
  events: TraceEvent[]
  artifacts: TraceArtifact[]
}> {
  const response = await axios.get(`${API_BASE}/workflows/executions/${executionId}/trace`)
  return response.data
}

/**
 * 获取 Trace spans
 */
export async function getTraceSpans(traceId: string): Promise<TraceSpan[]> {
  const response = await axios.get(`${API_BASE}/workflows/traces/${traceId}/spans`)
  return response.data.spans || []
}

/**
 * 获取 Trace events
 */
export async function getTraceEvents(traceId: string, limit: number = 200): Promise<TraceEvent[]> {
  const response = await axios.get(`${API_BASE}/workflows/traces/${traceId}/events`, {
    params: { limit },
  })
  return response.data.events || []
}

/**
 * 获取 Trace artifacts
 */
export async function getTraceArtifacts(traceId: string, spanId?: string): Promise<TraceArtifact[]> {
  const response = await axios.get(`${API_BASE}/workflows/traces/${traceId}/artifacts`, {
    params: { span_id: spanId },
  })
  return response.data.artifacts || []
}


export async function getExecutions(
  projectId: string,
  status?: WorkflowStatus,
  limit: number = 50,
  offset: number = 0,
  workflowId?: string,
): Promise<WorkflowExecutionHistoryRow[]> {
  const response = await axios.get(`${API_BASE}/workflows/executions`, {
    params: { project_id: projectId, status, limit, offset, workflow_id: workflowId },
  })
  return response.data
}

/**
 * 暂停执行
 */
export async function pauseExecution(
  executionId: string,
): Promise<{ success: boolean; message: string; execution?: WorkflowExecution | null }> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/pause`)
  return response.data
}

/**
 * 恢复执行
 */
export async function resumeExecution(
  executionId: string,
): Promise<{ success: boolean; message: string; execution?: WorkflowExecution | null }> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/resume`)
  return response.data
}

export async function recoverExecution(
  executionId: string,
  request: WorkflowRecoveryRequest = {},
): Promise<WorkflowRecoveryResponse> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/recover`, request)
  return response.data
}

export async function getFailedNodeDiagnosis(
  executionId: string,
  nodeId?: string,
): Promise<WorkflowFailureDiagnosis> {
  const response = await axios.get(`${API_BASE}/workflows/executions/${executionId}/failed-node-diagnosis`, {
    params: { node_id: nodeId },
  })
  return response.data
}

export async function validateRemediation(
  executionId: string,
  request: WorkflowRemediationRequest,
): Promise<Record<string, any>> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/remediations/validate`, request)
  return response.data
}

export async function remediateAndRecoverExecution(
  executionId: string,
  request: WorkflowRemediationRequest,
): Promise<WorkflowRemediationResponse> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/remediate-and-recover`, request)
  return response.data
}

export async function confirmDiscussion(
  executionId: string,
  approved: boolean,
  feedback?: string,
): Promise<{ success: boolean; message?: string; [key: string]: any }> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/confirm-discussion`, null, {
    params: { approved, feedback },
  })
  return response.data
}

/**
 * 取消执行
 */
export async function cancelExecution(
  executionId: string,
): Promise<{ success: boolean; message: string; execution?: WorkflowExecution | null }> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/cancel`)
  return response.data
}
