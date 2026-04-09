/**
 * Agent Configs API
 * 项目 Agent 配置管理接口
 */

import { api } from './client'

const API_BASE = ''

// ==================== 类型定义 ====================

export type ConfigOverrideType = 'prompt_replace' | 'variable_override' | 'slot_disable' | 'slot_enable' | 'model_change'

export interface SlotOverride {
  slot_name: string
  override_type: ConfigOverrideType
  prompt_template_id?: string
  variable_values?: Record<string, any>
  is_enabled?: boolean
  priority_override?: number
}

export interface ModelConfig {
  model_name: string
  temperature: number
  max_tokens?: number
  top_p?: number
  frequency_penalty?: number
  presence_penalty?: number
}

export interface AgentConfig {
  id: string
  project_id: string
  agent_type: string
  name: string
  description: string
  template_id?: string
  is_custom: boolean
  slot_overrides: SlotOverride[]
  custom_prompt_order?: string[]
  llm_config: ModelConfig
  is_active: boolean
  version: string
  usage_count: number
  last_used_at?: string
  created_at: string
  updated_at: string
}

export interface UpdateAgentConfigDTO {
  name?: string
  description?: string
  template_id?: string
  is_custom?: boolean
  slot_overrides?: SlotOverride[]
  custom_prompt_order?: string[]
  llm_config?: ModelConfig
  is_active?: boolean
  version?: string
}

export interface PreviewConfigResult {
  config_id: string
  project_id: string
  agent_type: string
  template?: {
    id: string
    name: string
    agent_type: string
  }
  is_custom: boolean
  llm_config: ModelConfig
  final_prompt: string
  prompt_length: number
  variables_used: Record<string, any>
}

// ==================== API 函数 ====================

/**
 * 获取项目所有 Agent 配置
 */
export async function getAgentConfigs(
  projectId: string,
  agentType?: string,
  isActive?: boolean,
  limit: number = 50,
  offset: number = 0
): Promise<AgentConfig[]> {
  const params = new URLSearchParams()
  if (agentType) params.append('agent_type', agentType)
  if (isActive !== undefined) params.append('is_active', String(isActive))
  params.append('limit', String(limit))
  params.append('offset', String(offset))

  return await api.get(`${API_BASE}/projects/${projectId}/agents?${params.toString()}`)
}

/**
 * 获取项目特定 Agent 类型的配置
 */
export async function getAgentConfig(projectId: string, agentType: string): Promise<AgentConfig> {
  return await api.get(`${API_BASE}/projects/${projectId}/agents/${agentType}`)
}

/**
 * 更新项目 Agent 配置
 */
export async function updateAgentConfig(
  projectId: string,
  agentType: string,
  dto: UpdateAgentConfigDTO
): Promise<{ success: boolean; message: string; config: AgentConfig }> {
  return await api.put(`${API_BASE}/projects/${projectId}/agents/${agentType}`, dto)
}

/**
 * 预览最终 prompt
 */
export async function previewAgentConfig(
  projectId: string,
  agentType: string,
  variables: Record<string, any> = {}
): Promise<PreviewConfigResult> {
  const params = new URLSearchParams()
  Object.entries(variables).forEach(([key, value]) => {
    params.append(key, String(value))
  })

  return await api.post(`${API_BASE}/projects/${projectId}/agents/${agentType}/preview?${params.toString()}`)
}

/**
 * 重置为模板默认
 */
export async function resetAgentConfigs(
  projectId: string,
  agentType?: string
): Promise<{
  success: boolean
  message: string
  results: Array<{
    config_id: string
    agent_type: string
    success: boolean
    message: string
  }>
}> {
  const params = new URLSearchParams()
  if (agentType) params.append('agent_type', agentType)

  return await api.post(`${API_BASE}/projects/${projectId}/agents/reset?${params.toString()}`)
}
