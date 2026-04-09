import { api } from './client'

export interface Chapter {
  id?: string
  title: string
  world_id?: string
  content?: string
  word_count?: number
  status: 'draft' | 'published' | 'archived' | 'in_progress' | 'completed'
  events?: string[]
  hooks_planted?: string[]
  hooks_resolved?: string[]
  main_plot_progress?: number
  reader_scores?: Record<string, number>
  created_at?: string
  updated_at?: string
  completed_at?: string
}

export interface CreateChapterDTO {
  title: string
  world_id?: string
  content?: string
  status?: string
}

export interface UpdateChapterDTO {
  title: string
  content?: string
  status?: string
  world_id?: string
}

export interface ReaderSimulationResult {
  scores: {
    opening: number
    pacing: number
    suspense: number
    character: number
    emotion: number
    flow: number
  }
  overall: number
  comments: string
  suggestions: string[]
}

export interface ChapterEvaluationResult {
  should_end: boolean
  reason: string
  missing_elements?: string[]
  suggested_continuation?: string
  scores: {
    info_gain: number
    suspense: number
    pacing: number
    completeness: number
  }
}

export async function getChapters(projectId?: string, worldId?: string) {
  const params: Record<string, string> = {}
  if (projectId) params.project_id = projectId
  if (worldId) params.world_id = worldId
  return await api.get<Chapter[]>('/plots/chapters', { params })
}

export async function getChapter(id: string) {
  return await api.get<Chapter>(`/plots/chapters/${id}`)
}

export async function createChapter(data: CreateChapterDTO) {
  return await api.post<Chapter>('/plots/chapters', data)
}

export async function updateChapter(id: string, data: UpdateChapterDTO) {
  return await api.put<Chapter>(`/plots/chapters/${id}`, data)
}

export async function deleteChapter(id: string) {
  return await api.delete(`/plots/chapters/${id}`)
}

export async function evaluateChapter(id: string) {
  return await api.post<ChapterEvaluationResult>(`/plots/chapters/${id}/evaluate`)
}

export async function simulateReader(id: string) {
  return await api.post<ReaderSimulationResult>(`/plots/chapters/${id}/reader-simulate`)
}

export async function getHooks(projectId?: string, status?: string) {
  const params: Record<string, string> = {}
  if (projectId) params.project_id = projectId
  if (status) params.status = status
  return await api.get<any[]>('/plots/hooks', { params })
}

export async function createHook(data: {
  title: string
  description?: string
  hook_type?: string
  related_characters?: string[]
  priority?: number
}) {
  return await api.post<any>('/plots/hooks', data)
}

export async function updateHookStatus(hookId: string, status: string) {
  return await api.put<any>(`/plots/hooks/${hookId}/status`, null, {
    params: { status },
  })
}
