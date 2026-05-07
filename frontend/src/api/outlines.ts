/**
 * 章节大纲 API 客户端
 * 与 Plot Outline Agent 交互
 */

import { api } from './client'

const API_BASE = '/outlines'

// ==================== 类型定义 ====================

export type EmotionType =
  | 'joy' | 'anger' | 'sadness' | 'fear' | 'surprise'
  | 'disgust' | 'anticipation' | 'trust' | 'tension' | 'relief' | 'neutral'

export type SceneType =
  | 'dialogue' | 'action' | 'description' | 'transition'
  | 'climax' | 'resolution' | 'flashback' | 'foreshadow'

export type ConflictLevel = 'low' | 'medium' | 'high' | 'critical'

export type OutlineStatus = 'draft' | 'approved' | 'in_writing' | 'completed' | 'revision' | 'rejected'

export interface EmotionPoint {
  position: number
  emotion: EmotionType
  intensity: number
  description?: string
}

export interface EmotionCurve {
  id: string
  chapter_number: number
  points: EmotionPoint[]
  dominant_emotion: EmotionType
  peak_emotion?: EmotionPoint
  pacing_type: string
  tension_buildup?: string
  reader_experience_goal?: string
}

export interface SceneOutline {
  id: string
  scene_number: number
  title: string
  scene_type: SceneType
  summary: string
  key_events: string[]
  participating_characters: string[]
  pov_character?: string
  location?: string
  time_of_day?: string
  emotion_start: EmotionType
  emotion_end: EmotionType
  emotion_arc: EmotionType[]
  conflict_level: ConflictLevel
  conflict_description?: string
  hooks_to_plant: string[]
  hooks_to_resolve: string[]
  estimated_words: number
  writing_hints: string[]
}

export interface ChapterOutline {
  id: string
  project_id: string
  chapter_number: number
  title: string
  summary: string
  status: OutlineStatus
  scenes: SceneOutline[]
  emotion_curve?: EmotionCurve
  chapter_goals: string[]
  plot_advancement?: string
  character_arcs: Record<string, string>
  hooks_planted: string[]
  hooks_resolved: string[]
  quality_metrics: Record<string, any>
  target_word_count: number
  estimated_word_count: number
  created_at: string
  updated_at: string
  approved_at?: string
  approved_by?: string
  previous_outline_id?: string
  next_outline_id?: string
}

export interface OutlineRevisionProposalResponse {
  outline: ChapterOutline
  revision_proposal: true
  approved_outline_id: string
  message: string
}

export interface OutlineVersionsResponse {
  chapter_number: number
  current_approved?: ChapterOutline | null
  pending_revisions: ChapterOutline[]
  rejected_revisions: ChapterOutline[]
  versions: ChapterOutline[]
  total: number
}

export type UpdateOutlineResponse = ChapterOutline | OutlineRevisionProposalResponse

export function isOutlineRevisionProposalResponse(
  response: UpdateOutlineResponse
): response is OutlineRevisionProposalResponse {
  return Boolean((response as OutlineRevisionProposalResponse).revision_proposal)
}

export interface OutlineStatistics {
  total_outlines: number
  total_target_words: number
  status_distribution: Record<string, number>
  average_scenes_per_chapter: number
  hooks_planned: number
  hooks_resolved: number
}

export interface GenerateOutlineRequest {
  project_id: string
  chapter_number: number
  context?: string
  previous_events?: string
  special_requirements?: string[]
}

export interface GenerateOutlineResponse {
  outline: ChapterOutline
  suggestions: string[]
  warnings: string[]
}

export interface ValidateOutlineResponse {
  valid: boolean
  issues: Array<{ type: string; message: string; severity: string }>
  suggestions: string[]
  score: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export interface ChatRequest {
  project_id: string
  chapter_number: number
  message: string
  context?: Record<string, any>
}

export interface PendingOutline {
  chapter_number: number
  title: string
  summary: string
  scenes?: Partial<SceneOutline>[]
  emotion_curve?: EmotionCurve
  chapter_goals?: string[]
  hooks_planted?: string[]
  hooks_resolved?: string[]
  target_word_count?: number
  character_arcs?: Record<string, string>
}

export interface SavePendingOutlineResult {
  chapter_number?: number
  status: 'saved' | 'failed'
  action?: 'created' | 'updated'
  outline_id?: string
  error_type?: 'validation_error' | 'save_error' | string
  error?: string
}

export interface SavePendingOutlinesResponse {
  success: boolean
  saved_count: number
  failed_count: number
  message: string
  results: SavePendingOutlineResult[]
}

export function extractSavePendingOutlinesFailure(error: any): SavePendingOutlinesResponse | null {
  const detail = error?.response?.data?.detail || error?.detail || error?.data
  if (!detail || typeof detail !== 'object') return null
  if (!Array.isArray(detail.results)) return null
  if (typeof detail.saved_count !== 'number' || typeof detail.failed_count !== 'number') return null
  return detail as SavePendingOutlinesResponse
}

export function formatSavePendingOutlinesFailure(result: SavePendingOutlinesResponse): string {
  const failed = result.results.filter(item => item.status === 'failed')
  if (failed.length === 0) return result.message
  const details = failed
    .map(item => `第${item.chapter_number ?? '?'}章：${item.error || item.error_type || '保存失败'}`)
    .join('\n')
  return `${result.message}\n${details}`
}

export interface ChatResponse {
  message: string
  outline_updates?: Partial<ChapterOutline>
  suggestions?: string[]
  pending_outlines?: PendingOutline[]
  saved_outline?: ChapterOutline
  saved_outlines?: ChapterOutline[]  // 多章大纲保存
}

export type ResourceRequirementSeverity = 'blocking' | 'advisory' | 'optional'
export type ResourceRequirementStatus = 'pending' | 'in_progress' | 'resolved' | 'ignored' | 'superseded'
export type ResourceRequirementResolutionMethod = 'bind_existing' | 'create_resource' | 'manual_resolved' | 'ignored'

export interface OutlineResourceRequirementMetadata {
  original_resource_type?: string
  resolution_method?: ResourceRequirementResolutionMethod
  resolution_recorded_at?: string
  previous_status?: ResourceRequirementStatus | string
  resolved_with_resource_type?: string
  reopened_at?: string
  [key: string]: any
}

export interface OutlineResourceRequirement {
  id: string
  project_id: string
  outline_id?: string | null
  outline_version_id?: string | null
  chapter_id?: string | null
  chapter_num?: number | null
  requirement_type: string
  original_resource_type?: string
  resource_name: string
  severity: ResourceRequirementSeverity
  status: ResourceRequirementStatus
  reason?: string
  suggested_payload?: Record<string, any>
  matched_resource_id?: string | null
  matched_resource_type?: string | null
  source_excerpt?: string
  source_agent?: string
  source_node_id?: string
  source_execution_id?: string
  metadata?: OutlineResourceRequirementMetadata
  created_at?: string
  updated_at?: string
  resolved_at?: string | null
}

export interface ChapterResourceReadiness {
  id?: string
  project_id: string
  outline_id?: string | null
  chapter_num: number
  blocking_total: number
  blocking_resolved: number
  advisory_total: number
  advisory_resolved: number
  readiness_status: 'not_audited' | 'blocked' | 'ready_with_warnings' | 'ready' | 'stale'
  last_audited_at?: string | null
  updated_at?: string
}

export interface ResourceSupplementDraft {
  requirement_id: string
  requirement_type?: string
  original_resource_type?: string
  resource_type: string
  resource_name?: string
  severity?: ResourceRequirementSeverity
  chapter_num?: number | null
  reason?: string
  draft_payload: Record<string, any>
  side_effect?: 'draft_only'
}

export interface ConfirmResourceSupplementResult {
  created: Array<{
    resource_type: string
    resource_id: string
    resource: Record<string, any>
    requirement?: OutlineResourceRequirement
    readiness?: ChapterResourceReadiness | null
  }>
  failed: Array<{
    requirement_id: string
    resource_type: string
    error: string
  }>
  readiness_by_chapter: Record<string, ChapterResourceReadiness | null>
  success: boolean
  message: string
}

// ==================== API 函数 ====================

/**
 * 获取大纲列表
 */
export async function getOutlines(projectId: string): Promise<{ outlines: ChapterOutline[]; total: number }> {
  return await api.get(`${API_BASE}?project_id=${projectId}`)
}

/**
 * 获取统计数据
 */
export async function getOutlineStatistics(projectId: string): Promise<OutlineStatistics> {
  return await api.get(`${API_BASE}/statistics?project_id=${projectId}`)
}

/**
 * 获取单章当前大纲
 */
export async function getOutline(projectId: string, chapterNumber: number): Promise<ChapterOutline> {
  return await api.get(`${API_BASE}/${chapterNumber}?project_id=${projectId}`)
}

/**
 * 按 ID 获取具体大纲版本
 */
export async function getOutlineById(projectId: string, outlineId: string): Promise<ChapterOutline> {
  return await api.get(`${API_BASE}/by-id/${outlineId}?project_id=${projectId}`)
}

/**
 * 获取单章所有大纲版本
 */
export async function getOutlineVersions(projectId: string, chapterNumber: number): Promise<OutlineVersionsResponse> {
  return await api.get(`${API_BASE}/${chapterNumber}/versions?project_id=${projectId}`)
}

/**
 * 生成大纲
 */
export async function generateOutline(
  projectId: string,
  chapterNumber: number,
  request: Partial<GenerateOutlineRequest>
): Promise<GenerateOutlineResponse> {
  return await api.post(`${API_BASE}/${chapterNumber}/generate?project_id=${projectId}`, request)
}

/**
 * 创建大纲
 */
export async function createOutline(
  projectId: string,
  chapterNumber: number,
  data: {
    title: string
    summary: string
    chapter_goals?: string[]
    target_word_count?: number
  }
): Promise<ChapterOutline> {
  return await api.post(`${API_BASE}/${chapterNumber}?project_id=${projectId}`, data)
}

/**
 * 更新大纲
 */
export async function updateOutline(
  projectId: string,
  chapterNumber: number,
  data: Partial<ChapterOutline>
): Promise<UpdateOutlineResponse> {
  return await api.put(`${API_BASE}/${chapterNumber}?project_id=${projectId}`, data)
}

/**
 * 验证大纲
 */
export async function validateOutline(
  projectId: string,
  chapterNumber: number
): Promise<ValidateOutlineResponse> {
  return await api.post(`${API_BASE}/${chapterNumber}/validate?project_id=${projectId}`)
}

/**
 * 审批大纲
 */
export async function approveOutline(
  projectId: string,
  chapterNumber: number,
  approvedBy: string
): Promise<ChapterOutline> {
  return await api.post(`${API_BASE}/${chapterNumber}/approve?project_id=${projectId}`, { approved_by: approvedBy })
}

/**
 * 按 ID 审批具体大纲版本
 */
export async function approveOutlineById(
  projectId: string,
  outlineId: string,
  approvedBy: string
): Promise<ChapterOutline> {
  return await api.post(`${API_BASE}/by-id/${outlineId}/approve?project_id=${projectId}`, { approved_by: approvedBy })
}

/**
 * 按 ID 拒绝修订提案
 */
export async function rejectOutlineRevisionById(
  projectId: string,
  outlineId: string
): Promise<ChapterOutline> {
  return await api.post(`${API_BASE}/by-id/${outlineId}/reject?project_id=${projectId}`, {})
}

/**
 * 删除大纲
 */
export async function deleteOutline(
  projectId: string,
  chapterNumber: number,
  options?: { softDeleteGeneratedChapters?: boolean }
): Promise<{ success: boolean; message: string; soft_deleted_chapters?: number }> {
  const params = new URLSearchParams({ project_id: projectId })
  if (options?.softDeleteGeneratedChapters) {
    params.set('soft_delete_generated_chapters', 'true')
  }
  return await api.delete(`${API_BASE}/${chapterNumber}?${params.toString()}`)
}

/**
 * 与 Agent 聊天
 */
export async function chatWithAgent(
  projectId: string,
  chapterNumber: number,
  message: string,
  context?: Record<string, any>
): Promise<ChatResponse> {
  return await api.post(`${API_BASE}/${chapterNumber}/chat?project_id=${projectId}`, {
    message,
    context,
  })
}

/**
 * 批量生成大纲
 */
export async function batchGenerateOutlines(
  projectId: string,
  startChapter: number,
  endChapter: number,
  options?: {
    context?: string
    parallel?: boolean
  }
): Promise<{ outlines: ChapterOutline[]; message: string }> {
  return await api.post(`${API_BASE}/batch-generate`, {
    project_id: projectId,
    start_chapter: startChapter,
    end_chapter: endChapter,
    ...options,
  })
}

/**
 * 保存待确认的大纲
 */
export async function savePendingOutlines(
  projectId: string,
  outlines: PendingOutline[]
): Promise<SavePendingOutlinesResponse> {
  return await api.post(`${API_BASE}/save-outlines?project_id=${projectId}`, {
    outlines,
  })
}

/**
 * 生成资源补全草案（只返回草案，不直接创建资源）
 */
export async function generateResourceSupplementDrafts(data: {
  project_id: string
  requirement_ids?: string[]
  outline_id?: string
  chapter_num?: number
  include_advisory?: boolean
}): Promise<{ drafts: ResourceSupplementDraft[]; total: number; side_effect: 'draft_only'; message: string }> {
  return await api.post(`${API_BASE}/resource-requirements/supplement-drafts`, data)
}

/**
 * 确认资源补全草案并创建资源
 */
export async function confirmResourceSupplementDrafts(data: {
  project_id: string
  drafts: Array<{
    requirement_id: string
    resource_type: string
    draft_payload: Record<string, any>
  }>
}): Promise<ConfirmResourceSupplementResult> {
  return await api.post(`${API_BASE}/resource-requirements/confirm-supplements`, data)
}

/**
 * 查询大纲资源需求
 */
export async function getOutlineResourceRequirements(
  projectId: string,
  filters?: {
    outline_id?: string
    chapter_num?: number
    status?: ResourceRequirementStatus
    severity?: ResourceRequirementSeverity
    requirement_type?: string
  }
): Promise<{ requirements: OutlineResourceRequirement[]; total: number }> {
  const params = new URLSearchParams({ project_id: projectId })
  if (filters?.outline_id) params.set('outline_id', filters.outline_id)
  if (filters?.chapter_num !== undefined) params.set('chapter_num', String(filters.chapter_num))
  if (filters?.status) params.set('status', filters.status)
  if (filters?.severity) params.set('severity', filters.severity)
  if (filters?.requirement_type) params.set('requirement_type', filters.requirement_type)
  return await api.get(`${API_BASE}/resource-requirements?${params.toString()}`)
}

/**
 * 查询章节资源 readiness
 */
export async function getChapterResourceReadiness(
  projectId: string,
  filters?: {
    outline_id?: string
    chapter_num?: number
    refresh?: boolean
  }
): Promise<{ readiness: ChapterResourceReadiness[]; total: number }> {
  const params = new URLSearchParams({ project_id: projectId })
  if (filters?.outline_id) params.set('outline_id', filters.outline_id)
  if (filters?.chapter_num !== undefined) params.set('chapter_num', String(filters.chapter_num))
  if (filters?.refresh) params.set('refresh', 'true')
  return await api.get(`${API_BASE}/resource-readiness?${params.toString()}`)
}

/**
 * 更新大纲资源需求状态
 */
export async function updateOutlineResourceRequirementStatus(
  requirementId: string,
  data: {
    status: ResourceRequirementStatus
    matched_resource_id?: string
    matched_resource_type?: string
    resolution_method?: ResourceRequirementResolutionMethod
  }
): Promise<{ requirement: OutlineResourceRequirement; readiness?: ChapterResourceReadiness | null }> {
  return await api.patch(`${API_BASE}/resource-requirements/${requirementId}`, data)
}
