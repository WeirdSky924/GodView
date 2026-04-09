/**
 * Prompts API
 * Prompt 模板管理接口
 */

import { api } from './client'

const API_BASE = '/prompts'

// ==================== 类型定义 ====================

export type PromptCategory =
  | 'role_definition'
  | 'function'
  | 'constraint'
  | 'style'
  | 'context'
  | 'output_format'

export interface PromptVariable {
  name: string
  type: 'string' | 'number' | 'boolean' | 'array' | 'object'
  description: string
  default?: any
  required: boolean
}

export interface PromptTemplate {
  id: string
  name: string
  description: string
  category: PromptCategory
  tags: string[]
  content: string
  variables: PromptVariable[]
  priority: number
  is_system: boolean
  version: string
  usage_count: number
  last_used_at?: string
  created_at: string
  updated_at: string
}

export interface PromptFilter {
  category?: PromptCategory
  tags?: string[]
  is_system?: boolean
  search?: string
  limit?: number
  offset?: number
}

export interface CreatePromptDTO {
  name: string
  description: string
  category: PromptCategory
  tags?: string[]
  content: string
  variables?: PromptVariable[]
  priority?: number
}

export interface UpdatePromptDTO {
  name?: string
  description?: string
  category?: PromptCategory
  tags?: string[]
  content?: string
  variables?: PromptVariable[]
  priority?: number
  version?: string
}

export interface RenderResult {
  template_id: string
  rendered_content: string
  variables_used: Record<string, any>
  missing_variables: string[]
}

// ==================== API 函数 ====================

/**
 * 获取 Prompt 列表
 */
export async function getPrompts(filters?: PromptFilter): Promise<PromptTemplate[]> {
  const params = new URLSearchParams()
  if (filters?.category) params.append('category', filters.category)
  if (filters?.tags) params.append('tags', filters.tags.join(','))
  if (filters?.is_system !== undefined) params.append('is_system', String(filters.is_system))
  if (filters?.search) params.append('search', filters.search)
  params.append('limit', String(filters?.limit || 50))
  params.append('offset', String(filters?.offset || 0))

  return await api.get(`${API_BASE}?${params.toString()}`)
}

/**
 * 创建 Prompt
 */
export async function createPrompt(dto: CreatePromptDTO): Promise<{ success: boolean; message: string; template: PromptTemplate }> {
  return await api.post(`${API_BASE}`, dto)
}

/**
 * 获取 Prompt 详情
 */
export async function getPrompt(promptId: string): Promise<PromptTemplate> {
  return await api.get(`${API_BASE}/${promptId}`)
}

/**
 * 更新 Prompt
 */
export async function updatePrompt(promptId: string, dto: UpdatePromptDTO): Promise<{ success: boolean; message: string; template: PromptTemplate }> {
  return await api.put(`${API_BASE}/${promptId}`, dto)
}

/**
 * 删除 Prompt
 */
export async function deletePrompt(promptId: string): Promise<{ success: boolean; message: string }> {
  return await api.delete(`${API_BASE}/${promptId}`)
}

/**
 * 搜索 Prompt
 */
export async function searchPrompts(query: string, category?: PromptCategory, limit: number = 50): Promise<PromptTemplate[]> {
  const params = new URLSearchParams()
  params.append('query', query)
  params.append('limit', String(limit))
  if (category) params.append('category', category)

  return await api.post(`${API_BASE}/search?${params.toString()}`)
}

/**
 * 获取分类列表
 */
export async function getCategories(): Promise<Record<string, number>> {
  return await api.get(`${API_BASE}/categories-list`)
}

/**
 * 渲染预览 Prompt
 */
export async function renderPrompt(promptId: string, variables: Record<string, any> = {}): Promise<RenderResult> {
  const params = new URLSearchParams()
  Object.entries(variables).forEach(([key, value]) => {
    params.append(key, String(value))
  })

  return await api.post(`${API_BASE}/${promptId}/render?${params.toString()}`)
}
