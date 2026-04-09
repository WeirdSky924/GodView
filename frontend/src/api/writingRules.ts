/**
 * Writing Rules API
 * 写作规则管理接口
 */

import { api } from './client'

const API_BASE = ''

// ==================== 类型定义 ====================

export type WritingRuleCategory = 'dialogue' | 'structure' | 'style' | 'pacing' | 'character' | 'plot' | 'format' | 'grammar'
export type RuleSeverity = 'required' | 'strong' | 'recommended' | 'optional' | 'info'

export interface WritingRule {
  id: string
  name: string
  description: string
  category: WritingRuleCategory
  severity: RuleSeverity
  content: string
  examples: string[]
  counter_examples?: string[]
  anti_patterns?: string[]
  tags: string[]
  is_system: boolean
  created_at?: string
  updated_at?: string
}

export interface WritingRuleSet {
  id: string
  name: string
  description: string
  rule_ids: string[]
  target_genre?: string
  tags: string[]
  is_system: boolean
  created_at: string
  updated_at: string
}

export interface ProjectWritingConfig {
  project_id: string
  enabled_rule_ids: string[]
  enabled_rule_set_ids: string[]
  custom_rules: WritingRule[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateWritingRuleDTO {
  name: string
  description: string
  category: WritingRuleCategory
  severity: RuleSeverity
  content: string
  examples?: string[]
  anti_patterns?: string[]
  tags?: string[]
}

export interface UpdateWritingRuleDTO {
  name?: string
  description?: string
  category?: WritingRuleCategory
  severity?: RuleSeverity
  content?: string
  examples?: string[]
  anti_patterns?: string[]
  tags?: string[]
}

export interface CreateWritingRuleSetDTO {
  name: string
  description: string
  rule_ids?: string[]
  target_genre?: string
  tags?: string[]
}

export interface UpdateProjectWritingConfigDTO {
  enabled_rule_ids?: string[]
  enabled_rule_set_ids?: string[]
  custom_rules?: CreateWritingRuleDTO[]
  is_active?: boolean
}

export interface PreviewResult {
  project_id: string
  prompt: string
  context: Record<string, any>
}

// ==================== API 函数 ====================

/**
 * 获取写作规则列表
 */
export async function getWritingRules(
  category?: WritingRuleCategory,
  severity?: RuleSeverity,
  tags?: string[],
  isSystem?: boolean,
  search?: string,
  source?: string,
  limit: number = 50,
  offset: number = 0
): Promise<WritingRule[]> {
  const params = new URLSearchParams()
  if (category) params.append('category', category)
  if (severity) params.append('severity', severity)
  if (tags) params.append('tags', tags.join(','))
  if (isSystem !== undefined) params.append('is_system', String(isSystem))
  if (search) params.append('search', search)
  if (source) params.append('source', source)
  params.append('limit', String(limit))
  params.append('offset', String(offset))

  return await api.get(`${API_BASE}/writing-rules?${params.toString()}`)
}

/**
 * 创建写作规则
 */
export async function createWritingRule(dto: CreateWritingRuleDTO): Promise<{ success: boolean; message: string; rule: WritingRule }> {
  return await api.post(`${API_BASE}/writing-rules`, dto)
}

/**
 * 获取写作规则详情
 */
export async function getWritingRule(ruleId: string): Promise<WritingRule> {
  return await api.get(`${API_BASE}/writing-rules/${ruleId}`)
}

/**
 * 更新写作规则
 */
export async function updateWritingRule(ruleId: string, dto: UpdateWritingRuleDTO): Promise<{ success: boolean; message: string }> {
  return await api.put(`${API_BASE}/writing-rules/${ruleId}`, dto)
}

/**
 * 删除写作规则
 */
export async function deleteWritingRule(ruleId: string): Promise<{ success: boolean; message: string }> {
  return await api.delete(`${API_BASE}/writing-rules/${ruleId}`)
}

/**
 * 获取写作规则集列表
 */
export async function getWritingRuleSets(
  category?: string,
  tags?: string[],
  targetGenre?: string,
  isSystem?: boolean,
  limit: number = 50,
  offset: number = 0
): Promise<WritingRuleSet[]> {
  const params = new URLSearchParams()
  if (category) params.append('category', category)
  if (tags) params.append('tags', tags.join(','))
  if (targetGenre) params.append('target_genre', targetGenre)
  if (isSystem !== undefined) params.append('is_system', String(isSystem))
  params.append('limit', String(limit))
  params.append('offset', String(offset))

  return await api.get(`${API_BASE}/writing-rule-sets?${params.toString()}`)
}

/**
 * 创建写作规则集
 */
export async function createWritingRuleSet(dto: CreateWritingRuleSetDTO): Promise<{ success: boolean; message: string; rule_set: WritingRuleSet }> {
  return await api.post(`${API_BASE}/writing-rule-sets`, dto)
}

/**
 * 获取写作规则集详情
 */
export async function getWritingRuleSet(ruleSetId: string): Promise<WritingRuleSet & { rules?: WritingRule[] }> {
  return await api.get(`${API_BASE}/writing-rule-sets/${ruleSetId}`)
}

/**
 * 更新写作规则集
 */
export async function updateWritingRuleSet(ruleSetId: string, dto: CreateWritingRuleSetDTO): Promise<{ success: boolean; message: string }> {
  return await api.put(`${API_BASE}/writing-rule-sets/${ruleSetId}`, dto)
}

/**
 * 删除写作规则集
 */
export async function deleteWritingRuleSet(ruleSetId: string): Promise<{ success: boolean; message: string }> {
  return await api.delete(`${API_BASE}/writing-rule-sets/${ruleSetId}`)
}

/**
 * 获取项目写作配置
 */
export async function getProjectWritingConfig(projectId: string): Promise<ProjectWritingConfig> {
  return await api.get(`${API_BASE}/projects/${projectId}/writing-config`)
}

/**
 * 更新项目写作配置
 */
export async function updateProjectWritingConfig(
  projectId: string,
  dto: UpdateProjectWritingConfigDTO
): Promise<{ success: boolean; message: string }> {
  return await api.put(`${API_BASE}/projects/${projectId}/writing-config`, dto)
}

/**
 * 预览写作规则 prompt
 */
export async function previewWritingPrompt(
  projectId: string,
  context?: Record<string, any>
): Promise<PreviewResult> {
  return await api.post(`${API_BASE}/projects/${projectId}/writing-config/preview`, context)
}

// ==================== Agent Prompt API ====================

export type AgentPromptType = 'summarizer' | 'master_plotter' | 'hook_manager' | 'writer' | 'evaluator' | 'proc_gen' | 'character' | 'setting'

export interface AgentTemplateSummary {
  id: string
  name: string
  slots: string[]
  model: string
  temperature: number
}

export interface AgentPromptPreview {
  agent_type: AgentPromptType
  project_id?: string
  prompt: string
  prompt_length: number
}

/**
 * 获取所有 Agent 模板摘要
 */
export async function getAgentTemplateSummaries(): Promise<Record<string, AgentTemplateSummary>> {
  const result = await api.get<{ templates: Record<string, AgentTemplateSummary> }>(`${API_BASE}/agent-prompts`)
  return result.templates
}

/**
 * 预览 Agent 完整 system prompt
 */
export async function previewAgentPrompt(
  agentType: AgentPromptType,
  projectId?: string,
  variables?: Record<string, any>
): Promise<AgentPromptPreview> {
  const params = new URLSearchParams()
  if (projectId) params.append('project_id', projectId)

  return await api.post(`${API_BASE}/agent-prompts/${agentType}/preview?${params.toString()}`, variables)
}
