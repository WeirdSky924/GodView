/**
 * Agent Templates API
 * Agent 模板管理接口
 */

import axios from 'axios'

const API_BASE = '/api/agent-templates'

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
  default_model: string
  default_temperature: number
  default_max_tokens: number
  tags: string[]
  is_system: boolean
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
  default_model?: string
  default_temperature?: number
  default_max_tokens?: number
  tags?: string[]
}

export interface UpdateAgentTemplateDTO {
  name?: string
  description?: string
  prompt_slots?: PromptSlot[]
  default_prompt_order?: string[]
  default_model?: string
  default_temperature?: number
  default_max_tokens?: number
  tags?: string[]
  version?: string
}

export interface PreviewResult {
  template_id: string
  template_name: string
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

  const response = await axios.get(`${API_BASE}?${params.toString()}`)
  return response.data
}

/**
 * 创建 Agent 模板
 */
export async function createAgentTemplate(dto: CreateAgentTemplateDTO): Promise<{ success: boolean; message: string; template: AgentTemplate }> {
  const response = await axios.post(`${API_BASE}`, dto)
  return response.data
}

/**
 * 获取 Agent 模板详情
 */
export async function getAgentTemplate(templateId: string): Promise<AgentTemplate> {
  const response = await axios.get(`${API_BASE}/${templateId}`)
  return response.data
}

/**
 * 更新 Agent 模板
 */
export async function updateAgentTemplate(templateId: string, dto: UpdateAgentTemplateDTO): Promise<{ success: boolean; message: string; template: AgentTemplate }> {
  const response = await axios.put(`${API_BASE}/${templateId}`, dto)
  return response.data
}

/**
 * 删除 Agent 模板
 */
export async function deleteAgentTemplate(templateId: string): Promise<{ success: boolean; message: string }> {
  const response = await axios.delete(`${API_BASE}/${templateId}`)
  return response.data
}

/**
 * 预览 Agent 模板渲染结果
 */
export async function previewAgentTemplate(templateId: string, variables: Record<string, any> = {}): Promise<PreviewResult> {
  const params = new URLSearchParams()
  Object.entries(variables).forEach(([key, value]) => {
    params.append(key, String(value))
  })

  const response = await axios.post(`${API_BASE}/${templateId}/preview?${params.toString()}`)
  return response.data
}

/**
 * 按类型获取 Agent 模板
 */
export async function getAgentTemplateByType(agentType: AgentType): Promise<AgentTemplate> {
  const response = await axios.get(`${API_BASE}/by-type/${agentType}`)
  return response.data
}
