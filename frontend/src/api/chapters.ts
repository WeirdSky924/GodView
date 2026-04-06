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

export async function getChapters(worldId?: string) {
  const params = worldId ? { world_id: worldId } : {}
  const response = await api.get<Chapter[]>('/plots/chapters', { params })
  return response.data
}

export async function getChapter(id: string) {
  const response = await api.get<Chapter>(`/plots/chapters/${id}`)
  return response.data
}

export async function createChapter(data: CreateChapterDTO) {
  const response = await api.post<Chapter>('/plots/chapters', data)
  return response.data
}

export async function updateChapter(id: string, data: UpdateChapterDTO) {
  const response = await api.put<Chapter>(`/plots/chapters/${id}`, data)
  return response.data
}

export async function deleteChapter(id: string) {
  const response = await api.delete(`/plots/chapters/${id}`)
  return response.data
}

export async function evaluateChapter(id: string) {
  const response = await api.post<ChapterEvaluationResult>(`/plots/chapters/${id}/evaluate`)
  return response.data
}

export async function simulateReader(id: string) {
  const response = await api.post<ReaderSimulationResult>(`/plots/chapters/${id}/reader-simulate`)
  return response.data
}

export async function getHooks(status?: string) {
  const params = status ? { status } : {}
  const response = await api.get<any[]>('/plots/hooks', { params })
  return response.data
}

export async function createHook(data: {
  title: string
  description?: string
  hook_type?: string
  related_characters?: string[]
  priority?: number
}) {
  const response = await api.post<any>('/plots/hooks', data)
  return response.data
}

export async function updateHookStatus(hookId: string, status: string) {
  const response = await api.put<any>(`/plots/hooks/${hookId}/status`, null, {
    params: { status },
  })
  return response.data
}
