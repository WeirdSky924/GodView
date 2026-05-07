/**
 * Prompts API
 * Prompt 模板管理接口
 */

import { api } from './client'
import { getCachedQuery, invalidateQueryCache, type QueryCacheOptions } from './queryCache'

const API_BASE = '/prompts'

// ==================== 类型定义 ====================

// 与后端 PromptCategory 枚举保持一致
export type PromptCategory =
  | 'base'        // 基础 prompt
  | 'role'        // 角色定义
  | 'function'    // 功能规范
  | 'value'       // 价值观/风格
  | 'output'      // 输出格式
  | 'constraint'  // 约束条件

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

export interface PromptFilter {
  category?: PromptCategory
  tags?: string[]
  is_system?: boolean
  search?: string
  limit?: number
  offset?: number
  cache?: QueryCacheOptions
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

  const query = params.toString()
  return await getCachedQuery(
    `prompts:list:${query}`,
    () => api.get(`${API_BASE}?${query}`),
    { ttlMs: 30 * 1000, ...filters?.cache }
  )
}

/**
 * 创建 Prompt
 */
export async function createPrompt(dto: CreatePromptDTO): Promise<{ success: boolean; message: string; template: PromptTemplate }> {
  const result = await api.post<{ success: boolean; message: string; template: PromptTemplate }>(`${API_BASE}`, dto)
  invalidatePromptCaches()
  return result
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
  const result = await api.put<{ success: boolean; message: string; template: PromptTemplate }>(`${API_BASE}/${promptId}`, dto)
  invalidatePromptCaches()
  return result
}

/**
 * 删除 Prompt
 */
export async function deletePrompt(promptId: string): Promise<{ success: boolean; message: string }> {
  const result = await api.delete<{ success: boolean; message: string }>(`${API_BASE}/${promptId}`)
  invalidatePromptCaches()
  return result
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
export async function getCategories(options: QueryCacheOptions = {}): Promise<Record<string, number>> {
  return await getCachedQuery(
    'prompts:categories',
    () => api.get(`${API_BASE}/categories-list`),
    { ttlMs: 5 * 60 * 1000, ...options }
  )
}

/**
 * 同步 prompts/ 目录下的 MD 文件到数据库
 */
export async function syncPromptMdFiles(): Promise<MdSyncResult> {
  const result = await api.post<MdSyncResult>(`${API_BASE}/sync-md-files`)
  invalidatePromptCaches()
  return result
}

/**
 * 获取 prompts/skills MD 文件统计
 */
export async function getPromptMdStats(options: QueryCacheOptions = {}): Promise<MdStatsResponse> {
  return await getCachedQuery(
    'prompts:md-stats',
    () => api.get(`${API_BASE}/md-stats`),
    { ttlMs: 5 * 60 * 1000, ...options }
  )
}

export function invalidatePromptCaches(): void {
  invalidateQueryCache('prompts')
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
