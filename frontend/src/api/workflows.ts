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
): Promise<{ success: boolean; message: string; execution_id: string; workflow_id: string }> {
  const response = await axios.post(
    `${API_BASE}/workflows/${workflowId}/execute`,
    initialContext || {},
    { params: { project_id: projectId } },
  )
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
 * 获取执行列表
 */
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

/**
 * 取消执行
 */
export async function cancelExecution(
  executionId: string,
): Promise<{ success: boolean; message: string }> {
  const response = await axios.post(`${API_BASE}/workflows/executions/${executionId}/cancel`)
  return response.data
}
