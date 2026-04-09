/**
 * Token 使用统计 API
 */

import { api } from './client'

// ==================== 类型定义 ====================

export interface TokenUsageSummary {
  total_tokens: number
  total_input_tokens: number
  total_output_tokens: number
  total_cost: number
  record_count: number
  by_category: Record<string, number>
  by_model: Record<string, number>
}

export interface ProjectTokenStats {
  project_id: string
  project_name: string
  total_tokens: number
  total_cost: number
  today_tokens: number
  today_cost: number
  week_tokens: number
  week_cost: number
  month_tokens: number
  month_cost: number
  updated_at: string
}

export interface DailyTokenStats {
  date: string
  total_tokens: number
  input_tokens: number
  output_tokens: number
  cost: number
  record_count: number
}

// ==================== API 函数 ====================

/**
 * 获取项目 Token 使用摘要
 */
export async function getProjectTokenSummary(
  projectId: string,
  startDate?: string,
  endDate?: string
): Promise<TokenUsageSummary> {
  const params = new URLSearchParams()
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)

  const query = params.toString() ? `?${params.toString()}` : ''
  return await api.get<TokenUsageSummary>(
    `/token-usage/projects/${projectId}/summary${query}`
  )
}

/**
 * 获取项目 Token 统计
 */
export async function getProjectTokenStats(projectId: string): Promise<ProjectTokenStats> {
  return await api.get<ProjectTokenStats>(
    `/token-usage/projects/${projectId}/stats`
  )
}

/**
 * 获取项目每日 Token 统计
 */
export async function getProjectDailyStats(
  projectId: string,
  days: number = 7
): Promise<DailyTokenStats[]> {
  return await api.get<DailyTokenStats[]>(
    `/token-usage/projects/${projectId}/daily?days=${days}`
  )
}

/**
 * 获取所有项目的 Token 统计
 */
export async function getAllTokenStats(): Promise<ProjectTokenStats[]> {
  return await api.get<ProjectTokenStats[]>('/token-usage/stats')
}

/**
 * 获取按场景分组的 Token 统计
 */
export async function getTokenByCategory(
  projectId: string,
  startDate?: string,
  endDate?: string
): Promise<{ project_id: string; by_category: Record<string, number>; total_tokens: number }> {
  const params = new URLSearchParams()
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)

  const query = params.toString() ? `?${params.toString()}` : ''
  return await api.get(
    `/token-usage/projects/${projectId}/by-category${query}`
  )
}

/**
 * 获取按模型分组的 Token 统计
 */
export async function getTokenByModel(
  projectId: string,
  startDate?: string,
  endDate?: string
): Promise<{ project_id: string; by_model: Record<string, number>; total_tokens: number }> {
  const params = new URLSearchParams()
  if (startDate) params.append('start_date', startDate)
  if (endDate) params.append('end_date', endDate)

  const query = params.toString() ? `?${params.toString()}` : ''
  return await api.get(
    `/token-usage/projects/${projectId}/by-model${query}`
  )
}
