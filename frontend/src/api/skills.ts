/**
 * Skills API
 * Agent Skill 管理接口
 */

import { api } from './client'

const API_BASE = '/skills'

// ==================== 类型定义 ====================

export type SkillType = 'prompt' | 'function' | 'workflow' | 'knowledge'
export type SkillStatus = 'draft' | 'active' | 'deprecated'

export interface SkillParameter {
  name: string
  type: string
  description: string
  default?: any
  required: boolean
  options?: any[]
}

export interface Skill {
  id: string
  name: string
  description: string
  skill_type: SkillType
  prompt_template?: string
  function_code?: string
  workflow_steps?: Array<Record<string, any>>
  knowledge_content?: string
  parameters: SkillParameter[]
  tags: string[]
  version: string
  status: SkillStatus
  creator_project_id?: string
  creator_agent_id?: string
  creator_user_id?: string
  usage_count: number
  last_used_at?: string
  created_at: string
  updated_at: string
}

export interface SkillAssignment {
  id: string
  skill_id: string
  project_id: string
  agent_id: string
  custom_parameters?: Record<string, any>
  priority: number
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
  created_at: string
}

export interface SkillTestResult {
  success: boolean
  output?: string
  error?: string
  execution_time_ms?: number
}

export interface SkillStats {
  total_skills: number
  total_assignments: number
  total_usage: number
  by_type: Record<string, number>
  by_status: Record<string, number>
}

export interface CreateSkillDTO {
  name: string
  description: string
  skill_type: SkillType
  prompt_template?: string
  function_code?: string
  workflow_steps?: Array<Record<string, any>>
  knowledge_content?: string
  parameters?: SkillParameter[]
  tags?: string[]
  creator_project_id?: string
  creator_agent_id?: string
}

export interface UpdateSkillDTO {
  name?: string
  description?: string
  prompt_template?: string
  function_code?: string
  workflow_steps?: Array<Record<string, any>>
  knowledge_content?: string
  parameters?: SkillParameter[]
  tags?: string[]
  version?: string
  status?: SkillStatus
}

export interface AssignSkillDTO {
  skill_id: string
  project_id: string
  agent_id: string
  custom_parameters?: Record<string, any>
  priority?: number
}

// ==================== API 函数 ====================

/**
 * 获取 Skill 列表
 */
export async function getSkills(
  skillType?: SkillType,
  status?: SkillStatus,
  tags?: string[],
  search?: string,
  limit: number = 50,
  offset: number = 0
): Promise<Skill[]> {
  const params = new URLSearchParams()
  if (skillType) params.append('skill_type', skillType)
  if (status) params.append('status', status)
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
 * 分配 Skill 给 Agent
 */
export async function assignSkill(dto: AssignSkillDTO): Promise<SkillAssignment> {
  return await api.post(`${API_BASE}/assign`, dto)
}

/**
 * 取消 Skill 分配
 */
export async function unassignSkill(
  skillId: string,
  projectId: string,
  agentId: string
): Promise<{ success: boolean; message: string }> {
  return await api.delete(`${API_BASE}/assign?skill_id=${skillId}&project_id=${projectId}&agent_id=${agentId}`)
}

/**
 * 获取 Skill 的分配列表
 */
export async function getSkillAssignments(skillId: string): Promise<SkillAssignment[]> {
  return await api.get(`${API_BASE}/${skillId}/assignments`)
}

/**
 * 获取 Agent 已分配的 Skills
 */
export async function getAgentSkills(projectId: string, agentId: string): Promise<Skill[]> {
  return await api.get(`${API_BASE}/agent/${projectId}/${agentId}`)
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
