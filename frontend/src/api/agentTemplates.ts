/**
 * Agent Templates API
 * Agent 模板管理接口
 */

import { api } from './client'

const API_BASE = '/agent-templates'

// ==================== 类型定义 ====================

export type AgentType =
  | 'character'
  | 'setting'
  | 'summarizer'
  | 'master_plotter'
  | 'hook_manager'
  | 'writer'
  | 'evaluator'
  | 'proc_gen'
  | 'event_generator'
  | 'dungeon_generator'
  | 'world_map_manager'

export interface PromptSlot {
  slot_name: string
  description: string
  prompt_template_id?: string
  required: boolean
  is_enabled: boolean
  priority: number
  variable_overrides: Record<string, any>
}

export interface AgentTemplate {
  id: string
  name: string
  description: string
  agent_type: AgentType
  prompt_slots: PromptSlot[]
  default_prompt_order: string[]
  tags: string[]
  is_system: boolean
  is_optional: boolean
  is_enabled: boolean
  version: string
  created_at: string
  updated_at: string
}

export interface CreateAgentTemplateDTO {
  name: string
  description: string
  agent_type: AgentType
  prompt_slots?: PromptSlot[]
  default_prompt_order?: string[]
  tags?: string[]
}

export interface UpdateAgentTemplateDTO {
  name?: string
  description?: string
  prompt_slots?: PromptSlot[]
  default_prompt_order?: string[]
  tags?: string[]
  version?: string
}

export interface PreviewResult {
  template_id: string
  template_name: string
  project_id: string | null
  rendered_prompts: Array<{
    slot_name: string
    description: string
    content: string
  }>
  final_prompt: string
}

// ==================== API 函数 ====================

/**
 * 获取 Agent 模板列表
 */
export async function getAgentTemplates(
  agentType?: AgentType,
  isSystem?: boolean,
  tags?: string[],
  limit: number = 50,
  offset: number = 0
): Promise<AgentTemplate[]> {
  const params = new URLSearchParams()
  if (agentType) params.append('agent_type', agentType)
  if (isSystem !== undefined) params.append('is_system', String(isSystem))
  if (tags) params.append('tags', tags.join(','))
  params.append('limit', String(limit))
  params.append('offset', String(offset))

  return await api.get(`${API_BASE}?${params.toString()}`)
}

/**
 * 创建 Agent 模板
 */
export async function createAgentTemplate(dto: CreateAgentTemplateDTO): Promise<{ success: boolean; message: string; template: AgentTemplate }> {
  return await api.post(`${API_BASE}`, dto)
}

/**
 * 获取 Agent 模板详情
 */
export async function getAgentTemplate(templateId: string): Promise<AgentTemplate> {
  return await api.get(`${API_BASE}/${templateId}`)
}

/**
 * 更新 Agent 模板
 */
export async function updateAgentTemplate(templateId: string, dto: UpdateAgentTemplateDTO): Promise<{ success: boolean; message: string; template: AgentTemplate }> {
  return await api.put(`${API_BASE}/${templateId}`, dto)
}

/**
 * 删除 Agent 模板
 */
export async function deleteAgentTemplate(templateId: string): Promise<{ success: boolean; message: string }> {
  return await api.delete(`${API_BASE}/${templateId}`)
}

/**
 * 预览 Agent 模板渲染结果
 */
export async function previewAgentTemplate(
  templateId: string,
  projectId?: string,
  variables: Record<string, any> = {}
): Promise<PreviewResult> {
  const params = new URLSearchParams()
  if (projectId) {
    params.append('project_id', projectId)
  }
  Object.entries(variables).forEach(([key, value]) => {
    params.append(key, String(value))
  })

  return await api.post(`${API_BASE}/${templateId}/preview?${params.toString()}`)
}

/**
 * 按类型获取 Agent 模板
 */
export async function getAgentTemplateByType(agentType: AgentType): Promise<AgentTemplate> {
  return await api.get(`${API_BASE}/by-type/${agentType}`)
}

/**
 * 切换可选 Agent 模板的启用状态
 */
export async function toggleAgentTemplate(templateId: string, enabled: boolean): Promise<{ success: boolean; message: string; template: AgentTemplate }> {
  return await api.post(`${API_BASE}/${templateId}/toggle?enabled=${enabled}`)
}

/**
 * 获取核心 Agent 类型列表
 */
export async function getCoreAgentTypes(): Promise<string[]> {
  return await api.get(`${API_BASE}/core/list`)
}

/**
 * 获取可选 Agent 类型列表
 */
export async function getOptionalAgentTypes(): Promise<string[]> {
  return await api.get(`${API_BASE}/optional/list`)
}
