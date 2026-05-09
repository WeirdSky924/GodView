/**
 * Workflow Node Types API
 * 动态获取工作流节点类型
 */

import { api } from './client'

const API_BASE = '/workflows'

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

export interface AgentTypeOption {
  value: string
  label: string
}

export const FALLBACK_AGENT_TYPE_OPTIONS: AgentTypeOption[] = [
  { value: 'setting', label: '设定 Agent' },
  { value: 'writer', label: '作家 Agent' },
  { value: 'master_plotter', label: '总编剧 Agent' },
  { value: 'plotter', label: '编剧 Agent' },
  { value: 'character', label: '角色 Agent' },
  { value: 'summarizer', label: '摘要 Agent' },
  { value: 'evaluator', label: '评估 Agent' },
  { value: 'hook_manager', label: '伏笔 Agent' },
  { value: 'event_generator', label: '事件 Agent' },
  { value: 'world_map_manager', label: '地图 Agent' },
  { value: 'proc_gen', label: '过程生成 Agent' },
  { value: 'dungeon_generator', label: '副本生成 Agent' },
  { value: 'plot_outline', label: '章节大纲 Agent' },
  { value: 'scene_coordinator', label: '场景协调 Agent' },
]

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

/**
 * 从 node-types payload 构建 Agent 类型下拉选项
 *
 * 角色 Agent 在属性面板/私聊面板里统一显示为“角色 Agent”，
 * 避免将项目角色列表展开成重复选项。
 */
export function getAgentTypeOptions(nodeTypes?: WorkflowNodeTypes | null): AgentTypeOption[] {
  if (!nodeTypes) {
    return FALLBACK_AGENT_TYPE_OPTIONS
  }

  const options: AgentTypeOption[] = []
  const seen = new Set<string>()

  for (const node of [...nodeTypes.agent_nodes, ...nodeTypes.character_nodes]) {
    if (!node.agent_type) continue

    const value = node.agent_type
    if (seen.has(value)) continue
    seen.add(value)

    options.push({
      value,
      label: value === 'character' ? '角色 Agent' : node.label,
    })
  }

  return options.length > 0 ? options : FALLBACK_AGENT_TYPE_OPTIONS
}
