/**
 * Agent Templates API
 * Agent 模板管理接口
 */

import { api } from './client'
import { getCachedQuery, invalidateQueryCache, type QueryCacheOptions } from './queryCache'
import { invalidateAgentConfigCaches } from './agentConfigs'
import { withStartupRetry } from './startupRetry'

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
  | 'scene_coordinator'
  | 'plot_outline'
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

export interface SkillSlot {
  slot_name: string
  description: string
  skill_id?: string
  is_enabled: boolean
  is_required: boolean
  priority: number
  variable_overrides: Record<string, any>
  execution_condition?: string
}

export interface AgentTemplate {
  id: string
  name: string
  description: string
  agent_type: AgentType
  scenario: string
  prompt_slots: PromptSlot[]
  skill_slots: SkillSlot[]
  default_prompt_order: string[]
  default_skill_order: string[]
  default_model?: string | null
  default_temperature: number
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
  scenario?: string
  prompt_slots?: PromptSlot[]
  skill_slots?: SkillSlot[]
  default_prompt_order?: string[]
  default_skill_order?: string[]
  default_model?: string | null
  default_temperature?: number
  tags?: string[]
  is_system?: boolean
  is_optional?: boolean
  is_enabled?: boolean
}

export interface UpdateAgentTemplateDTO {
  name?: string
  description?: string
  agent_type?: AgentType
  scenario?: string
  prompt_slots?: PromptSlot[]
  skill_slots?: SkillSlot[]
  default_prompt_order?: string[]
  default_skill_order?: string[]
  default_model?: string | null
  default_temperature?: number
  tags?: string[]
  is_system?: boolean
  is_optional?: boolean
  is_enabled?: boolean
  version?: string
}

export interface PreviewRenderTrace {
  agent_type: AgentType | string
  scenario?: string | null
  project_id?: string | null
  template_id?: string | null
  template_scenario?: string | null
  config_id?: string | null
  prompt_ids: string[]
  skill_ids: string[]
  skills?: {
    agent_type?: AgentType | string
    scenario?: string | null
    skill_ids?: string[]
    source?: string
    scope?: Record<string, any>
    fallbacks_used?: string[]
    deprecated_sources_used?: string[]
  } | null
  writing_rule_ids: string[]
  context_blocks: string[]
  fallbacks_used: string[]
  deprecated_sources_used: string[]
  writing_rules?: {
    project_id?: string | null
    writing_rule_ids?: string[]
    always_rule_ids?: string[]
    retrieved_rules?: Array<{
      id?: string
      name?: string
      severity?: string
      reason?: string
      score?: number
    }>
    resolved_scope?: Record<string, any> | null
    query?: string
    fallbacks_used?: string[]
    deprecated_sources_used?: string[]
    error?: string
  } | null
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
  render_trace?: PreviewRenderTrace
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
  offset: number = 0,
  scenario?: string,
  options: QueryCacheOptions = {}
): Promise<AgentTemplate[]> {
  const params = new URLSearchParams()
  if (agentType) params.append('agent_type', agentType)
  if (scenario) params.append('scenario', scenario)
  if (isSystem !== undefined) params.append('is_system', String(isSystem))
  tags?.forEach((tag) => params.append('tags', tag))
  params.append('limit', String(limit))
  params.append('offset', String(offset))

  const query = params.toString()
  return await getCachedQuery(
    `agent-templates:list:${query || 'default'}`,
    () => withStartupRetry(
      () => api.get(`${API_BASE}${query ? `?${query}` : ''}`),
      { label: 'agent templates' }
    ),
    { ttlMs: 30 * 1000, ...options }
  )
}

/**
 * 创建 Agent 模板
 */
export async function createAgentTemplate(dto: CreateAgentTemplateDTO): Promise<{ success: boolean; message: string; template: AgentTemplate }> {
  const result = await api.post<{ success: boolean; message: string; template: AgentTemplate }>(`${API_BASE}`, dto)
  invalidateAgentTemplateCaches()
  return result
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
  const result = await api.put<{ success: boolean; message: string; template: AgentTemplate }>(`${API_BASE}/${templateId}`, dto)
  invalidateAgentTemplateCaches()
  return result
}

/**
 * 删除 Agent 模板
 */
export async function deleteAgentTemplate(templateId: string): Promise<{ success: boolean; message: string }> {
  const result = await api.delete<{ success: boolean; message: string }>(`${API_BASE}/${templateId}`)
  invalidateAgentTemplateCaches()
  return result
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

  const query = params.toString()
  return await api.post(`${API_BASE}/${templateId}/preview${query ? `?${query}` : ''}`, variables)
}

/**
 * 按类型获取 Agent 模板
 */
export async function getAgentTemplateByType(agentType: AgentType, scenario?: string): Promise<AgentTemplate> {
  const params = new URLSearchParams()
  if (scenario) params.append('scenario', scenario)
  const query = params.toString()
  return await api.get(`${API_BASE}/by-type/${agentType}${query ? `?${query}` : ''}`)
}

/**
 * 切换可选 Agent 模板的启用状态
 */
export async function toggleAgentTemplate(
  templateId: string,
  enabled: boolean,
  projectId?: string,
): Promise<{ success: boolean; message: string; template: AgentTemplate; project_config?: unknown }> {
  const params = new URLSearchParams()
  params.append('enabled', String(enabled))
  if (projectId) params.append('project_id', projectId)
  const result = await api.post<{ success: boolean; message: string; template: AgentTemplate; project_config?: unknown }>(`${API_BASE}/${templateId}/toggle?${params.toString()}`)
  invalidateAgentTemplateCaches()
  if (projectId) invalidateAgentConfigCaches(projectId)
  return result
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

/**
 * Agent 类型元数据
 */
export interface AgentTypeMetadata {
  type: AgentType
  label: string
  description: string
  icon: string
  is_core: boolean
  is_optional: boolean
}

/**
 * 获取所有 Agent 类型的元数据（用于动态生成 UI）
 */
export async function getAgentTypesMetadata(options: QueryCacheOptions = {}): Promise<AgentTypeMetadata[]> {
  return await getCachedQuery(
    'agent-templates:type-metadata',
    () => withStartupRetry(
      () => api.get(`${API_BASE}/types/metadata`),
      { label: 'agent type metadata' }
    ),
    { ttlMs: 5 * 60 * 1000, ...options }
  )
}

export function invalidateAgentTemplateCaches(): void {
  invalidateQueryCache('agent-templates')
}
