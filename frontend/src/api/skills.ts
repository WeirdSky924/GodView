/**
 * Skills API
 * Agent Skill 管理接口
 */

import { api } from './client'

const API_BASE = '/skills'

// ==================== 类型定义 ====================

export type SkillType = 'prompt' | 'function' | 'workflow' | 'knowledge'
export type SkillStatus = 'draft' | 'active' | 'deprecated'
export type SkillCategory =
  | 'writing' | 'editing' | 'style'
  | 'plotting' | 'pacing' | 'conflict'
  | 'character' | 'dialogue' | 'ooc_check'
  | 'foreshadowing' | 'hook'
  | 'evaluation' | 'reader_sim'
  | 'world_building' | 'setting'
  | 'analysis' | 'summary'
  | 'discussion' | 'performance'
  | 'general'

export interface SkillParameter {
  name: string
  type: string
  description: string
  default?: any
  required: boolean
  options?: any[]
  validation?: Record<string, any>
}

export interface SkillOutputSpec {
  name: string
  type: string
  description: string
  required: boolean
}

export interface Skill {
  id: string
  name: string
  description: string

  // 类型和分类
  skill_type: SkillType
  category: SkillCategory
  tags: string[]

  // 适用范围
  applicable_agent_types: string[]  // 空数组表示所有 Agent 都可用

  // 内容定义
  prompt_template?: string
  prompt_template_id?: string
  function_code?: string
  workflow_steps?: Array<Record<string, any>>
  knowledge_content?: string

  // 参数和输出
  parameters: SkillParameter[]
  output_spec: SkillOutputSpec[]

  // 执行配置
  temperature: number
  max_tokens?: number
  timeout: number
  retry_count: number

  // 优先级和状态
  priority: number
  status: SkillStatus
  is_system: boolean
  is_enabled: boolean
  is_composable: boolean

  // 创建来源
  creator_project_id?: string
  creator_agent_id?: string
  creator_user_id?: string

  // 元数据
  version: string
  author: string
  examples: Array<Record<string, any>>

  // 使用统计
  usage_count: number
  last_used_at?: string
  created_at: string
  updated_at: string
}

export interface SkillAssignment {
  id: string
  skill_id: string
  agent_type: string
  scenario: string

  slot_name: string
  custom_parameters?: Record<string, any>
  variable_overrides: Record<string, any>
  priority: number

  // 执行条件
  execution_condition?: string
  is_enabled: boolean
  is_required: boolean

  // 分配信息
  assigned_by: string
  assigned_at: string
}

export interface SkillExecutionLog {
  id: string
  skill_id: string
  project_id?: string
  agent_id?: string
  input_params: Record<string, any>
  output_result?: string
  success: boolean
  error_message?: string
  execution_time_ms?: number
  token_usage?: Record<string, number>
  created_at: string
}

export interface SkillTestResult {
  success: boolean
  output?: string
  error?: string
  execution_time_ms?: number
  token_usage?: Record<string, number>
}

export interface SkillStats {
  total_skills: number
  total_assignments: number
  total_usage: number
  by_type: Record<string, number>
  by_status: Record<string, number>
}

export interface MdAssetStats {
  total: number
  by_category?: Record<string, number>
  by_type?: Record<string, number>
}

export interface MdStatsResponse {
  prompts?: MdAssetStats
  skills?: MdAssetStats
}

export interface MdSyncFileResult {
  file_path?: string | null
  id?: string | null
  status: 'synced' | 'skipped' | 'error' | string
  message: string
}

export interface MdSyncResult {
  success: boolean
  message: string
  result: {
    synced?: number
    skipped?: number
    errors?: number
    error?: number
    files?: MdSyncFileResult[]
  }
}

export interface CreateSkillDTO {
  name: string
  description?: string
  skill_type: SkillType
  category?: SkillCategory
  tags?: string[]
  applicable_agent_types?: string[]

  prompt_template?: string
  prompt_template_id?: string
  function_code?: string
  workflow_steps?: Array<Record<string, any>>
  knowledge_content?: string

  parameters?: SkillParameter[]
  output_spec?: SkillOutputSpec[]

  temperature?: number
  max_tokens?: number
  timeout?: number

  priority?: number
  is_composable?: boolean
  examples?: Array<Record<string, any>>

  creator_project_id?: string
  creator_agent_id?: string
  creator_user_id?: string
}

export interface UpdateSkillDTO {
  name?: string
  description?: string
  category?: SkillCategory
  tags?: string[]
  applicable_agent_types?: string[]

  prompt_template?: string
  prompt_template_id?: string
  function_code?: string
  workflow_steps?: Array<Record<string, any>>
  knowledge_content?: string

  parameters?: SkillParameter[]
  output_spec?: SkillOutputSpec[]

  temperature?: number
  max_tokens?: number
  timeout?: number

  priority?: number
  status?: SkillStatus
  is_enabled?: boolean
  is_composable?: boolean
  examples?: Array<Record<string, any>>
}

export interface AssignSkillDTO {
  skill_id: string
  agent_type: string
  scenario?: string
  slot_name?: string
  custom_parameters?: Record<string, any>
  variable_overrides?: Record<string, any>
  priority?: number
  execution_condition?: string
  is_enabled?: boolean
  is_required?: boolean
}

// ==================== API 函数 ====================

/**
 * 获取 Skill 列表
 */
export async function getSkills(
  skillType?: SkillType,
  status?: SkillStatus,
  category?: SkillCategory,
  agentType?: string,
  tags?: string[],
  search?: string,
  limit: number = 50,
  offset: number = 0
): Promise<Skill[]> {
  const params = new URLSearchParams()
  if (skillType) params.append('skill_type', skillType)
  if (status) params.append('status', status)
  if (category) params.append('category', category)
  if (agentType) params.append('agent_type', agentType)
  if (tags) params.append('tags', tags.join(','))
  if (search) params.append('search', search)
  params.append('limit', String(limit))
  params.append('offset', String(offset))

  return await api.get(`${API_BASE}/?${params.toString()}`)
}

/**
 * 创建 Skill
 */
export async function createSkill(dto: CreateSkillDTO): Promise<Skill> {
  return await api.post(`${API_BASE}/`, dto)
}

/**
 * 获取 Skill 详情
 */
export async function getSkill(skillId: string): Promise<Skill> {
  return await api.get(`${API_BASE}/${skillId}`)
}

/**
 * 更新 Skill
 */
export async function updateSkill(skillId: string, dto: UpdateSkillDTO): Promise<Skill> {
  return await api.put(`${API_BASE}/${skillId}`, dto)
}

/**
 * 删除 Skill
 */
export async function deleteSkill(skillId: string): Promise<{ success: boolean; message: string }> {
  return await api.delete(`${API_BASE}/${skillId}`)
}

/**
 * 搜索 Skill
 */
export async function searchSkills(query: string, limit: number = 10): Promise<Skill[]> {
  return await api.post(`${API_BASE}/search?query=${encodeURIComponent(query)}&limit=${limit}`)
}

/**
 * AI 生成 Skill
 */
export async function generateSkill(description: string, skillType: SkillType = 'prompt'): Promise<Skill> {
  return await api.post(`${API_BASE}/generate?description=${encodeURIComponent(description)}&skill_type=${skillType}`)
}

/**
 * 测试 Skill
 */
export async function testSkill(skillId: string, parameters: Record<string, any> = {}): Promise<SkillTestResult> {
  return await api.post(`${API_BASE}/${skillId}/test`, parameters)
}

/**
 * 执行 Skill
 */
export async function executeSkill(
  skillId: string,
  parameters: Record<string, any> = {},
  projectId?: string,
  agentId?: string
): Promise<SkillTestResult> {
  const params = new URLSearchParams()
  if (projectId) params.append('project_id', projectId)
  if (agentId) params.append('agent_id', agentId)

  return await api.post(`${API_BASE}/${skillId}/execute?${params.toString()}`, parameters)
}

/**
 * 分配 Skill 给 Agent 模板
 */
export async function assignSkill(dto: AssignSkillDTO): Promise<SkillAssignment> {
  return await api.post(`${API_BASE}/assign`, dto)
}

/**
 * 取消 Skill 分配
 */
export async function unassignSkill(
  skillId: string,
  agentType: string
): Promise<{ success: boolean; message: string }> {
  return await api.delete(`${API_BASE}/${skillId}/assign/${agentType}`)
}

/**
 * 获取 Skill 的分配列表
 */
export async function getSkillAssignments(skillId: string): Promise<SkillAssignment[]> {
  return await api.get(`${API_BASE}/${skillId}/assignments`)
}

/**
 * 获取 Agent 模板的 Skills
 */
export async function getAgentTypeSkills(agentType: string, scenario?: string): Promise<Skill[]> {
  const params = new URLSearchParams()
  if (scenario) params.append('scenario', scenario)
  const query = params.toString()
  return await api.get(`${API_BASE}/agents/${agentType}/skills${query ? `?${query}` : ''}`)
}

/**
 * 获取 Skill 执行日志
 */
export async function getSkillLogs(
  skillId: string,
  projectId?: string,
  agentId?: string,
  limit: number = 50
): Promise<SkillExecutionLog[]> {
  const params = new URLSearchParams()
  if (projectId) params.append('project_id', projectId)
  if (agentId) params.append('agent_id', agentId)
  params.append('limit', String(limit))

  return await api.get(`${API_BASE}/${skillId}/logs?${params.toString()}`)
}

/**
 * 获取所有执行日志
 */
export async function getAllLogs(
  projectId?: string,
  agentId?: string,
  limit: number = 50
): Promise<SkillExecutionLog[]> {
  const params = new URLSearchParams()
  if (projectId) params.append('project_id', projectId)
  if (agentId) params.append('agent_id', agentId)
  params.append('limit', String(limit))

  return await api.get(`${API_BASE}/logs/all?${params.toString()}`)
}

/**
 * 获取 Skill 统计
 */
export async function getSkillsStats(): Promise<SkillStats> {
  return await api.get(`${API_BASE}/stats/overview`)
}

/**
 * 同步 skills/ 目录下的 MD 文件到数据库
 */
export async function syncSkillMdFiles(): Promise<MdSyncResult> {
  return await api.post(`${API_BASE}/sync-md-files`)
}

/**
 * 获取 prompts/skills MD 文件统计
 */
export async function getSkillMdStats(): Promise<MdStatsResponse> {
  return await api.get(`${API_BASE}/md-stats`)
}

/**
 * 初始化默认 Skills
 */
export async function initializeDefaultSkills(): Promise<{
  success: boolean
  message: string
  result: {
    skills_created: number
    skills_skipped: number
    assignments_created: number
  }
}> {
  return await api.post(`${API_BASE}/initialize`)
}

/**
 * 获取所有 Skill 类别
 */
export async function getSkillCategories(): Promise<string[]> {
  return await api.get(`${API_BASE}/categories`)
}

/**
 * 获取所有 Skill 类型
 */
export async function getSkillTypes(): Promise<string[]> {
  return await api.get(`${API_BASE}/types`)
}
