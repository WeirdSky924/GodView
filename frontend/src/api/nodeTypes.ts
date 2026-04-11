/**
 * Workflow Node Types API
 * 动态获取工作流节点类型
 */

import { api } from './client'

const API_BASE = '/workflow'

// ==================== 类型定义 ====================

export type NodeCategory = 'agent' | 'control' | 'interaction'

export interface NodeTypeConfigHint {
  type?: string
  options?: string[]
  default?: any
  description?: string
}

export interface NodeTypeInfo {
  type: string
  label: string
  description: string
  category: NodeCategory
  icon: string
  color: string
  agent_type?: string
  is_system: boolean
  supports_multiple?: boolean
  config_hints?: Record<string, NodeTypeConfigHint>

  // 角色 Agent 专属
  character_id?: string
  character_name?: string
  importance_tier?: number
}

export interface WorkflowNodeTypes {
  agent_nodes: NodeTypeInfo[]
  interaction_nodes: NodeTypeInfo[]
  control_nodes: NodeTypeInfo[]
  character_nodes: NodeTypeInfo[]
}

// ==================== API 函数 ====================

/**
 * 获取工作流节点类型
 * @param projectId 项目ID，用于获取项目角色Agent
 */
export async function getWorkflowNodeTypes(projectId?: string): Promise<WorkflowNodeTypes> {
  const params = new URLSearchParams()
  if (projectId) {
    params.append('project_id', projectId)
  }
  const query = params.toString() ? `?${params.toString()}` : ''
  return await api.get(`${API_BASE}/node-types${query}`)
}

/**
 * 获取所有可用的 Agent 节点类型（包括系统Agent和角色Agent）
 */
export async function getAvailableAgentNodes(projectId?: string): Promise<NodeTypeInfo[]> {
  const data = await getWorkflowNodeTypes(projectId)
  return [...data.agent_nodes, ...data.character_nodes]
}
