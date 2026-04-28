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
  duration_ms?: number
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
  request_id?: string
  request_hash?: string
  operation_id?: string
  trace_id?: string
  cancel_requested?: boolean
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

/**
 * 获取当前活跃执行
 */
export async function getActiveWorkflowExecution(
  projectId: string,
  workflowId?: string,
): Promise<{ success: boolean; execution: WorkflowExecution | null }> {
  const response = await axios.get(`${API_BASE}/workflows/executions/active`, {
    params: { project_id: projectId, workflow_id: workflowId },
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
): Promise<WorkflowExecution[]> {
  const response = await axios.get(`${API_BASE}/workflows/executions`, {
    params: { project_id: projectId, status, limit, offset },
  })
  return response.data
}

/**
 * 暂停执行
 */
export async function pauseExecution(
  executionId: string,
): Promise<{ success: boolean; message: string }> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/pause`)
  return response.data
}

/**
 * 恢复执行
 */
export async function resumeExecution(
  executionId: string,
): Promise<{ success: boolean; message: string }> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/resume`)
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
): Promise<{ success: boolean; message: string }> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/cancel`)
  return response.data
}
