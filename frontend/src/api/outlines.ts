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

export type OutlineStatus = 'draft' | 'approved' | 'in_writing' | 'completed' | 'revision'

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

export interface ChatResponse {
  message: string
  outline_updates?: Partial<ChapterOutline>
  suggestions?: string[]
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
 * 获取单章大纲
 */
export async function getOutline(projectId: string, chapterNumber: number): Promise<ChapterOutline> {
  return await api.get(`${API_BASE}/${chapterNumber}?project_id=${projectId}`)
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
): Promise<ChapterOutline> {
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
 * 删除大纲
 */
export async function deleteOutline(
  projectId: string,
  chapterNumber: number
): Promise<{ success: boolean; message: string }> {
  return await api.delete(`${API_BASE}/${chapterNumber}?project_id=${projectId}`)
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
