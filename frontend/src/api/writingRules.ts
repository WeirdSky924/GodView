/**
 * Writing Rules API
 * 写作规则管理接口
 */

import axios from 'axios'

const API_BASE = '/api'

// ==================== 类型定义 ====================

export type WritingRuleCategory = 'dialogue' | 'structure' | 'style' | 'pacing'
export type RuleSeverity = 'required' | 'recommended' | 'optional'

export interface WritingRule {
  id: string
  name: string
  description: string
  category: WritingRuleCategory
  severity: RuleSeverity
  content: string
  examples: string[]
  anti_patterns: string[]
  tags: string[]
  is_system: boolean
  created_at: string
  updated_at: string
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
  limit: number = 50,
  offset: number = 0
): Promise<WritingRule[]> {
  const params = new URLSearchParams()
  if (category) params.append('category', category)
  if (severity) params.append('severity', severity)
  if (tags) params.append('tags', tags.join(','))
  if (isSystem !== undefined) params.append('is_system', String(isSystem))
  if (search) params.append('search', search)
  params.append('limit', String(limit))
  params.append('offset', String(offset))

  const response = await axios.get(`${API_BASE}/writing-rules?${params.toString()}`)
  return response.data
}

/**
 * 创建写作规则
 */
export async function createWritingRule(dto: CreateWritingRuleDTO): Promise<{ success: boolean; message: string; rule: WritingRule }> {
  const response = await axios.post(`${API_BASE}/writing-rules`, dto)
  return response.data
}

/**
 * 获取写作规则详情
 */
export async function getWritingRule(ruleId: string): Promise<WritingRule> {
  const response = await axios.get(`${API_BASE}/writing-rules/${ruleId}`)
  return response.data
}

/**
 * 更新写作规则
 */
export async function updateWritingRule(ruleId: string, dto: UpdateWritingRuleDTO): Promise<{ success: boolean; message: string }> {
  const response = await axios.put(`${API_BASE}/writing-rules/${ruleId}`, dto)
  return response.data
}

/**
 * 删除写作规则
 */
export async function deleteWritingRule(ruleId: string): Promise<{ success: boolean; message: string }> {
  const response = await axios.delete(`${API_BASE}/writing-rules/${ruleId}`)
  return response.data
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

  const response = await axios.get(`${API_BASE}/writing-rule-sets?${params.toString()}`)
  return response.data
}

/**
 * 创建写作规则集
 */
export async function createWritingRuleSet(dto: CreateWritingRuleSetDTO): Promise<{ success: boolean; message: string; rule_set: WritingRuleSet }> {
  const response = await axios.post(`${API_BASE}/writing-rule-sets`, dto)
  return response.data
}

/**
 * 获取项目写作配置
 */
export async function getProjectWritingConfig(projectId: string): Promise<ProjectWritingConfig> {
  const response = await axios.get(`${API_BASE}/projects/${projectId}/writing-config`)
  return response.data
}

/**
 * 更新项目写作配置
 */
export async function updateProjectWritingConfig(
  projectId: string,
  dto: UpdateProjectWritingConfigDTO
): Promise<{ success: boolean; message: string }> {
  const response = await axios.put(`${API_BASE}/projects/${projectId}/writing-config`, dto)
  return response.data
}

/**
 * 预览写作规则 prompt
 */
export async function previewWritingPrompt(
  projectId: string,
  context?: Record<string, any>
): Promise<PreviewResult> {
  const response = await axios.post(`${API_BASE}/projects/${projectId}/writing-config/preview`, context)
  return response.data
}
